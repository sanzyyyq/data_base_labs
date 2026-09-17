import numpy as np
import pandas as pd

np.random.seed(42)

vyst_mo = pd.DataFrame(
    np.random.default_rng(0).standard_normal((50, 10)), columns=("col %d" % i for i in range(10))
)
vuz = pd.DataFrame(
    np.random.default_rng(0).standard_normal((50, 10)), columns=("col %d" % i for i in range(10))
)
grntirub = pd.DataFrame(
    np.random.default_rng(0).standard_normal((50, 10)), columns=("col %d" % i for i in range(10))
)
def data(table):
    if table == "VYST_MO":
        return vyst_mo
    elif table == "VUZ":
        return vuz
    elif table == "GRNTIRUB":
        return grntirub
