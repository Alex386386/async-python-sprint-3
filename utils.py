import random
import string

from constants import VALUE_FOR_RANDOMIZER


def generate_unique_code():
    all_chars = string.ascii_letters + string.digits
    return ''.join(
        random.choice(all_chars) for _ in range(VALUE_FOR_RANDOMIZER)
    )
