Data is organized in 4 modules (Module1-4) with the same structure

Inside the module there are:
- 1 directory per camera (with camera id/macaddr) [E581CB can be ignored]
  path:macaddr/YYYY-MM-DD/pic_001/HH.MM.SS[R][0@0][0].jpg
- configs: config changes (path:macaddr/datetime) as json of NEW settings
- detections: triggered events (path:macaddr/day/time_macaddr) as json
- logs (only most recent, likely safe to ignore for now)
- overviews: daily overview videos [redundant with images, skip for now]
- videos: triggered videos (path:macaddr/day/time_macaddr.mp4

Rough numbers
28 cameras per module (some cameras are in >1 module, 73 total)
~68 days of data
~1440 images per day
~2.74 million images

Tables
- cameras [N=112]
  id, macaddr, module

- stills [N=4455413]
  id, camera table row id, datetime, path

- configs [N=52479]
  id, camera table row id, datetime, path

- detections [N=2804663]
  id, camera table row id, datetime, path

- videos [N=467216]
  id, camera table row id, datetime, path


merge with weather data
merge with manual 'camera position + species' data
