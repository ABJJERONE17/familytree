"""
Database models for the family tree.

Two tables only:
  Person   - one row per family member; father/mother point back at Person.
  Marriage - one row per couple; links two Person rows.

Nothing that can be calculated is stored: age, generation, siblings, children
and spouses are all derived from these two tables.
"""
from datetime import date
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import F, Q
from django.templatetags.static import static
from PIL import Image, ImageOps

THUMBNAIL_SIZE = (320, 320)


class Gender(models.TextChoices):
    MALE = "M", "Male"
    FEMALE = "F", "Female"
    OTHER = "O", "Other"


class DatePrecision(models.TextChoices):
    """How much of a stored date is actually known."""

    DAY = "D", "Exact date"
    YEAR = "Y", "Year only"


# --------------------------------------------------------------------------
# Small date helpers (shared by Person and Marriage)
# --------------------------------------------------------------------------
def normalise_partial_date(value, precision):
    """Year-only dates are always stored as 1 January of that year."""
    if value and precision == DatePrecision.YEAR:
        return value.replace(month=1, day=1)
    return value


def format_partial_date(value, precision):
    """'14 Mar 1987' for exact dates, '1987' for year-only dates."""
    if not value:
        return ""
    if precision == DatePrecision.YEAR:
        return str(value.year)
    return f"{value.day} {value:%b %Y}"


def years_between(start, end):
    """Whole years from start to end (the usual 'age' calculation)."""
    had_birthday = (end.month, end.day) >= (start.month, start.day)
    return end.year - start.year - (0 if had_birthday else 1)


# --------------------------------------------------------------------------
# Person
# --------------------------------------------------------------------------
class Person(models.Model):
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60, blank=True)
    nickname = models.CharField(max_length=60, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices)

    birth_date = models.DateField(null=True, blank=True)
    birth_date_precision = models.CharField(
        max_length=1,
        choices=DatePrecision.choices,
        default=DatePrecision.DAY,
        help_text="If only the year is known, pick 'Year only' and enter any day in that year.",
    )
    death_date = models.DateField(
        null=True, blank=True, help_text="Leave empty if the person is alive."
    )
    death_date_precision = models.CharField(
        max_length=1,
        choices=DatePrecision.choices,
        default=DatePrecision.DAY,
        help_text="If only the year is known, pick 'Year only' and enter any day in that year.",
    )

    birthplace = models.CharField(max_length=100, blank=True)
    current_city = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    biography = models.TextField(blank=True, help_text="One short paragraph.")

    photo = models.ImageField(upload_to="people/photos/", blank=True)
    # Filled in automatically from `photo` in save(); never edited by hand.
    photo_thumb = models.ImageField(upload_to="people/thumbs/", blank=True, editable=False)

    # SET_NULL: deleting a parent keeps the children, just without that link.
    father = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children_of_father",
        limit_choices_to={"gender": Gender.MALE},
    )
    mother = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children_of_mother",
        limit_choices_to={"gender": Gender.FEMALE},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name_plural = "people"
        # father/mother get an index automatically because they are foreign keys.
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="person_name_idx"),
            models.Index(fields=["birth_date"], name="person_birth_idx"),
            models.Index(fields=["death_date"], name="person_death_idx"),
            models.Index(fields=["current_city"], name="person_city_idx"),
        ]
        # Enforced by the database itself, as a last line of defence.
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(birth_date__isnull=True)
                    | Q(death_date__isnull=True)
                    | Q(death_date__gte=F("birth_date"))
                ),
                name="person_death_not_before_birth",
            ),
        ]

    def __str__(self):
        years = self.birth_date.year if self.birth_date else "?"
        if self.death_date:
            years = f"{years}-{self.death_date.year}"
        return f"{self.full_name} ({years})"

    # ---- Derived values (never stored) ------------------------------------
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_alive(self):
        return self.death_date is None

    @property
    def age_is_approximate(self):
        """True when a year-only date is involved, so the age may be off by one."""
        if self.birth_date_precision == DatePrecision.YEAR:
            return True
        return bool(self.death_date) and self.death_date_precision == DatePrecision.YEAR

    @property
    def age(self):
        """Current age if alive, age at death if deceased, None if birth is unknown."""
        if not self.birth_date:
            return None
        end = self.death_date or date.today()
        if self.age_is_approximate:
            return end.year - self.birth_date.year
        return years_between(self.birth_date, end)

    @property
    def birth_display(self):
        return format_partial_date(self.birth_date, self.birth_date_precision)

    @property
    def death_display(self):
        return format_partial_date(self.death_date, self.death_date_precision)

    @property
    def life_summary(self):
        """'Age 42' for the living; 'Late · 14 Mar 1987 · aged 82' for the deceased."""
        age = self.age
        approx = "~" if self.age_is_approximate else ""
        if self.is_alive:
            return f"Age {approx}{age}" if age is not None else ""
        parts = ["Late", self.death_display]
        if age is not None:
            parts.append(f"aged {approx}{age}")
        return " · ".join(parts)

    @property
    def photo_url(self):
        """Thumbnail if there is a photo, otherwise the placeholder image."""
        if self.photo_thumb:
            return self.photo_thumb.url
        return static("tree/img/placeholder.svg")

    # ---- Relatives --------------------------------------------------------
    def children(self):
        return Person.objects.filter(Q(father=self) | Q(mother=self)).order_by("birth_date")

    def siblings(self):
        """Everyone sharing at least one parent with this person."""
        shared = Q()
        if self.father_id:
            shared |= Q(father_id=self.father_id)
        if self.mother_id:
            shared |= Q(mother_id=self.mother_id)
        if not shared:
            return Person.objects.none()
        return Person.objects.filter(shared).exclude(pk=self.pk).order_by("birth_date")

    def marriages(self):
        return (
            Marriage.objects.filter(Q(partner1=self) | Q(partner2=self))
            .select_related("partner1", "partner2")
            .order_by("marriage_date")
        )

    def spouses(self):
        return [marriage.partner_of(self) for marriage in self.marriages()]

    def ancestor_ids(self):
        """IDs of every ancestor, using one query per generation."""
        seen = set()
        frontier = {pk for pk in (self.father_id, self.mother_id) if pk}
        while frontier:
            seen |= frontier
            rows = Person.objects.filter(pk__in=frontier).values_list("father_id", "mother_id")
            frontier = {pk for row in rows for pk in row if pk} - seen
        return seen

    # ---- Validation -------------------------------------------------------
    def clean(self):
        """Rules that involve more than one field. Called by full_clean()."""
        errors = {}
        today = date.today()

        if self.birth_date and self.birth_date > today:
            errors["birth_date"] = "Date of birth cannot be in the future."
        if self.death_date and self.death_date > today:
            errors["death_date"] = "Date of death cannot be in the future."

        if self.birth_date and self.death_date:
            year_only = DatePrecision.YEAR in (
                self.birth_date_precision,
                self.death_date_precision,
            )
            if year_only:
                too_early = self.death_date.year < self.birth_date.year
            else:
                too_early = self.death_date < self.birth_date
            if too_early:
                errors["death_date"] = "Date of death cannot be before date of birth."

        if self.father_id and self.mother_id and self.father_id == self.mother_id:
            errors["mother"] = "Father and mother cannot be the same person."

        for field, expected in (("father", Gender.MALE), ("mother", Gender.FEMALE)):
            parent_id = getattr(self, f"{field}_id")
            if not parent_id or field in errors:
                continue
            parent = getattr(self, field)
            if self.pk and parent_id == self.pk:
                errors[field] = "A person cannot be their own parent."
            elif parent.gender != expected:
                errors[field] = f"The {field} must be recorded as {expected.label.lower()}."
            elif (
                parent.birth_date
                and self.birth_date
                and parent.birth_date.year >= self.birth_date.year
            ):
                errors[field] = f"The {field} must be born before the child."

        # Cycle check: I must not appear among my own ancestors.
        # (A brand-new person has no pk yet, so nobody can descend from them.)
        if self.pk and not errors and self.pk in self.ancestor_ids():
            errors["father"] = (
                "This choice of parents would make the person their own ancestor."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.birth_date = normalise_partial_date(self.birth_date, self.birth_date_precision)
        self.death_date = normalise_partial_date(self.death_date, self.death_date_precision)
        # Django only validates automatically inside forms. Calling full_clean()
        # here means scripts and the CSV import obey the same rules as the admin.
        self.full_clean()
        self._sync_thumbnail()
        super().save(*args, **kwargs)

    # ---- Thumbnail --------------------------------------------------------
    def _sync_thumbnail(self):
        """Create, replace or remove the thumbnail to match `photo`."""
        if not self.photo:
            if self.photo_thumb:
                self.photo_thumb.delete(save=False)
            return
        # `_committed` is False only while a newly uploaded file is waiting to
        # be written to disk, i.e. the photo has just been added or changed.
        if self.photo._committed and self.photo_thumb:
            return

        source = self.photo.file
        source.seek(0)
        image = Image.open(source)
        image = ImageOps.exif_transpose(image)  # respect phone-camera rotation
        image = image.convert("RGB")
        image = ImageOps.fit(image, THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        source.seek(0)  # rewind so the original photo is still saved in full

        if self.photo_thumb:
            self.photo_thumb.delete(save=False)
        name = f"{Path(self.photo.name).stem}_thumb.jpg"
        self.photo_thumb.save(name, ContentFile(buffer.getvalue()), save=False)


# --------------------------------------------------------------------------
# Marriage
# --------------------------------------------------------------------------
class Marriage(models.Model):
    # CASCADE: a marriage row is meaningless once one partner is deleted.
    partner1 = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="marriages_as_partner1"
    )
    partner2 = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="marriages_as_partner2"
    )
    marriage_date = models.DateField(null=True, blank=True)
    marriage_date_precision = models.CharField(
        max_length=1, choices=DatePrecision.choices, default=DatePrecision.DAY
    )
    end_date = models.DateField(
        null=True, blank=True, help_text="Only if the marriage ended (e.g. divorce)."
    )

    class Meta:
        ordering = ["marriage_date"]
        indexes = [models.Index(fields=["marriage_date"], name="marriage_date_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=["partner1", "partner2"], name="marriage_unique_couple"
            ),
            models.CheckConstraint(
                condition=(
                    Q(marriage_date__isnull=True)
                    | Q(end_date__isnull=True)
                    | Q(end_date__gte=F("marriage_date"))
                ),
                name="marriage_end_not_before_start",
            ),
        ]

    def __str__(self):
        when = format_partial_date(self.marriage_date, self.marriage_date_precision)
        label = f"{self.partner1.full_name} & {self.partner2.full_name}"
        return f"{label} ({when})" if when else label

    @property
    def marriage_display(self):
        return format_partial_date(self.marriage_date, self.marriage_date_precision)

    def partner_of(self, person):
        """The other half of the couple."""
        return self.partner2 if self.partner1_id == person.pk else self.partner1

    def clean(self):
        if self.partner1_id and self.partner2_id:
            if self.partner1_id == self.partner2_id:
                raise ValidationError("A person cannot marry themselves.")
            # (A, B) and (B, A) are the same couple; block the mirrored duplicate.
            mirrored = Marriage.objects.filter(
                partner1_id=self.partner2_id, partner2_id=self.partner1_id
            ).exclude(pk=self.pk)
            if mirrored.exists():
                raise ValidationError("This couple already has a marriage record.")
        if self.marriage_date and self.end_date and self.end_date < self.marriage_date:
            raise ValidationError("End date cannot be before the marriage date.")

    def save(self, *args, **kwargs):
        self.marriage_date = normalise_partial_date(
            self.marriage_date, self.marriage_date_precision
        )
        self.full_clean()
        super().save(*args, **kwargs)
