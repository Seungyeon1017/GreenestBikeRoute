# GreenestBikeRoute
*Greenest Bike Route* is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone.

## Getting the data
Downloads the Heilbronn datasets from the [ATRAI API](https://hackathon.greencity.hn/resources/bike-data) into `data/` (~85 MB):

```bash
pip install requests
python -X utf8 data_download/download_data.py
```
