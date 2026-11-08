# Bundled resource notices

The Blue Marble JPEG was inherited from the basemap-data 2.0.0 distribution.
That release explicitly distinguishes its GSHHG-derived data (LGPL-3.0-or-later)
from its other files, including JPEG images (MIT). This project bundles the
JPEG, not the GSHHG coastlines, masks, rivers or political boundaries.
BASEMAP_DATA_MIT.txt preserves the applicable upstream notice. The unrelated
GPL/LGPL texts are therefore not included.

Sources checked:
- https://pypi.org/project/basemap-data/2.0.0/#description
- https://github.com/matplotlib/basemap/blob/v2.0.0/data/basemap_data/LICENSE.mit

The country geometry instead comes from Natural Earth via the GeoPandas legacy
dataset and is public domain. NASA imagery credit, asset history, and geographic
limitations remain in the bundled data/PROVENANCE.txt.
