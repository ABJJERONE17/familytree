"""
Create 50 sample people across 5 generations.

    python manage.py seed_family            # refuses to run if people already exist
    python manage.py seed_family --clear    # deletes everyone first, then seeds

Any file in <app>/management/commands/ becomes a "python manage.py <name>" command.
"""
import random
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tree.models import DatePrecision, Gender, Marriage, Person

FAMILY_NAME = "Varma"

MALE_NAMES = [
    "Arjun", "Vikram", "Rohan", "Karthik", "Anand", "Suresh", "Mahesh", "Rajesh",
    "Deepak", "Sanjay", "Vivek", "Nikhil", "Aditya", "Harish", "Ganesh", "Mohan",
    "Prakash", "Ramesh", "Sunil", "Varun", "Ashok", "Dinesh", "Girish", "Kiran",
    "Manoj", "Naveen", "Pranav", "Sachin", "Tarun", "Yash", "Gopal", "Hari",
]
FEMALE_NAMES = [
    "Lakshmi", "Meena", "Radha", "Sita", "Kavya", "Priya", "Anjali", "Divya",
    "Geetha", "Indira", "Jaya", "Kamala", "Latha", "Malini", "Nandini", "Padma",
    "Rekha", "Shanti", "Uma", "Vidya", "Asha", "Bhavna", "Chitra", "Deepa",
    "Gauri", "Isha", "Neha", "Pooja", "Sneha", "Tara", "Usha", "Revathi",
]
SPOUSE_SURNAMES = [
    "Iyer", "Nair", "Reddy", "Sharma", "Menon", "Pillai", "Rao", "Gupta",
    "Joshi", "Kulkarni", "Shetty", "Bose", "Desai", "Chopra", "Naidu", "Mishra",
    "Patel", "Kapoor", "Hegde", "Bhat",
]
CITIES = [
    "Chennai", "Bengaluru", "Mumbai", "Hyderabad", "Pune", "Kochi",
    "Coimbatore", "Delhi", "Madurai", "Mysuru",
]
OCCUPATIONS = [
    "teacher", "farmer", "doctor", "engineer", "accountant", "lawyer", "nurse",
    "shopkeeper", "bank officer", "civil servant", "tailor", "professor",
    "software developer", "architect", "journalist",
]
NICKNAMES = ["Appu", "Chinnu", "Babu", "Ammu", "Kannan", "Mani", "Raju", "Paapu"]

# How many children each blood relative has, per generation.
# None = that person stays unmarried.
# Totals: G1 2 + G2 6 + G3 12 + G4 20 + G5 10 = 50 people.
FOUNDER_CHILDREN = 3
CHILD_PLAN = {
    2: [2, 2, 2],
    3: [2, 2, 2, 2, 2, 2],
    4: [2, 1, None, 2, 1, None, 1, 1, None, 1, 1, None],
}


class Command(BaseCommand):
    help = "Create 50 sample people across 5 generations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete ALL existing people and marriages before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            Marriage.objects.all().delete()
            Person.objects.all().delete()
        elif Person.objects.exists():
            raise CommandError(
                "The database already has people. Run with --clear to replace them."
            )

        # A fixed seed gives the same family on every run.
        self.rng = random.Random(42)
        self.today = date.today()
        self.names = {
            Gender.MALE: self.rng.sample(MALE_NAMES, len(MALE_NAMES)),
            Gender.FEMALE: self.rng.sample(FEMALE_NAMES, len(FEMALE_NAMES)),
        }
        self.per_generation = {}

        # atomic(): if anything fails, nothing is saved (all or nothing).
        with transaction.atomic():
            founder = self.make_person(Gender.MALE, FAMILY_NAME, 1900, generation=1)
            spouse, married_in = self.marry(founder, generation=1)
            current = self.make_children(
                founder, spouse, married_in, FOUNDER_CHILDREN, generation=2
            )
            for generation in (2, 3, 4):
                next_generation = []
                for person, child_count in zip(current, CHILD_PLAN[generation]):
                    if child_count is None:
                        continue
                    spouse, married_in = self.marry(person, generation)
                    next_generation += self.make_children(
                        person, spouse, married_in, child_count, generation + 1
                    )
                current = next_generation

        for generation, count in sorted(self.per_generation.items()):
            self.stdout.write(f"  Generation {generation}: {count} people")
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {Person.objects.count()} people and "
                f"{Marriage.objects.count()} marriages."
            )
        )

    # ---- Builders ---------------------------------------------------------
    def random_date(self, year):
        return date(year, self.rng.randint(1, 12), self.rng.randint(1, 28))

    def make_person(self, gender, last_name, birth_year, generation, father=None, mother=None):
        rng = self.rng
        pool = self.names[gender]
        first_name = pool.pop() if pool else rng.choice(MALE_NAMES + FEMALE_NAMES)

        # Generation 1 uses year-only dates, like real old ancestors.
        precision = DatePrecision.YEAR if generation == 1 else DatePrecision.DAY

        death_year = birth_year + rng.randint(62, 95)
        deceased = death_year < self.today.year
        age_now = self.today.year - birth_year

        birthplace = father.current_city or father.birthplace if father else rng.choice(CITIES)
        city = rng.choice(CITIES)
        if age_now < 23 and not deceased:
            occupation = "student"
        else:
            occupation = rng.choice(OCCUPATIONS)
        nickname = rng.choice(NICKNAMES) if rng.random() < 0.25 else ""

        pronoun = "He" if gender == Gender.MALE else "She"
        if deceased:
            work = f"{pronoun} worked as a {occupation} and spent most of life in {city}."
        elif occupation == "student":
            work = f"{pronoun} is a student and lives in {city}."
        else:
            work = f"{pronoun} works as a {occupation} and lives in {city}."
        known_as = f", known to the family as {nickname}," if nickname else ""
        biography = (
            f"{first_name}{known_as} was born in {birthplace} in {birth_year}. {work} "
            "This is sample text created by the seed script."
        )

        person = Person(
            first_name=first_name,
            last_name=last_name,
            nickname=nickname,
            gender=gender,
            birth_date=self.random_date(birth_year),
            birth_date_precision=precision,
            death_date=self.random_date(death_year) if deceased else None,
            death_date_precision=precision,
            birthplace=birthplace,
            current_city="" if deceased else city,
            occupation=occupation,
            biography=biography,
            father=father,
            mother=mother,
        )
        person.save()  # runs full validation, see Person.save()
        self.per_generation[generation] = self.per_generation.get(generation, 0) + 1
        return person

    def marry(self, person, generation):
        """Create a spouse from outside the family plus the Marriage row."""
        rng = self.rng
        spouse_gender = Gender.FEMALE if person.gender == Gender.MALE else Gender.MALE
        spouse = self.make_person(
            spouse_gender,
            rng.choice(SPOUSE_SURNAMES),
            person.birth_date.year + rng.randint(-2, 2),
            generation,
        )
        married_in = person.birth_date.year + rng.randint(22, 26)
        Marriage(
            partner1=person,
            partner2=spouse,
            marriage_date=self.random_date(married_in),
            marriage_date_precision=(
                DatePrecision.YEAR if generation == 1 else DatePrecision.DAY
            ),
        ).save()
        return spouse, married_in

    def make_children(self, partner_a, partner_b, married_in, count, generation):
        father, mother = (
            (partner_a, partner_b) if partner_a.gender == Gender.MALE else (partner_b, partner_a)
        )
        children = []
        for index in range(count):
            birth_year = married_in + 1 + index * 2 + self.rng.randint(0, 1)
            gender = self.rng.choice([Gender.MALE, Gender.FEMALE])
            children.append(
                self.make_person(
                    gender, father.last_name, birth_year, generation, father=father, mother=mother
                )
            )
        return children
