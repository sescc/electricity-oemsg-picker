from .curated import Keppel, Sembcorp
from .flo import Flo
from .geneco import Geneco
from .pacificlight import PacificLight
from .senoko import Senoko
from .tuas import Tuas

# Mirrors https://www.openelectricitymarket.sg/residential/list-of-retailers (checked 2026-09-22)
ADAPTERS = [Flo(), Geneco(), Keppel(), PacificLight(), Sembcorp(), Senoko(), Tuas()]
OEM_LIST_URL = "https://www.openelectricitymarket.sg/residential/list-of-retailers"
