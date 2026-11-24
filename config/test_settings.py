import os
from copy import deepcopy

from .settings import *

DATABASES = deepcopy(DATABASES)

DATABASES["default"].update({
    "USER": os.environ["TEST_DB_USER"],
    "PASSWORD": os.environ["TEST_DB_PASSWORD"],
    "TEST": {
        "NAME": "test_ecommerce_db",
    },
})