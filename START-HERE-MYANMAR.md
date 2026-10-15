# စတင်အသုံးပြုရန် — Myanmar Hazard Monitor

ဒီ ZIP ကို အပြည့်အစုံဖြည်ပြီး ဖိုင်/ဖိုလ်ဒါဖွဲ့စည်းပုံကို မပြောင်းဘဲ အသုံးပြုပါ။ `index.html` က အဓိက website ဖြစ်ပြီး `demo.html` က UI စမ်းကြည့်ရန် ဖန်တီးထားသော **စိတ်ကူးယဉ် flood/landslide အချက်အလက်များ** ပါဝင်သည့် demo သာဖြစ်သည်။ အမှန်တကယ်သတိပေးချက်အဖြစ် မသုံးပါနှင့်။

## ၁။ ကွန်ပျူတာပေါ်မှာ စမ်းရန်

1. ZIP ကို Extract လုပ်ပါ။
2. VS Code မှာ ဖြည်ထားတဲ့ folder ကို Open လုပ်ပါ။
3. `Live Server` extension ထည့်ပါ။
4. `index.html` ကို right-click → **Open with Live Server** လုပ်ပါ။
5. Firefox/Chrome က ဖွင့်ပေးတဲ့ address ကို သုံးပါ။ အရင်သုံးခဲ့တဲ့ `127.0.0.1:8000` server ကိုရပ်ပြီး address အဟောင်းမဟုတ်ကြောင်း စစ်ပါ။

မြေပုံအတွက် CDN နဲ့ map tiles များက အင်တာနက်လိုအပ်သည်။ CDN မရလျှင် မြေပုံမတက်နိုင်သော်လည်း public-information panel မှ ရင်းမြစ်လင့်ခ်များကို ပြသရန် ကြိုးစားပါလိမ့်မည်။

## ၂။ GitHub Pages ပေါ် တင်ရန်

1. ZIP ကို Extract လုပ်ပါ။
2. GitHub repository ထဲက project ရှိ ဖိုင်များကို ဒီ folder ထဲက ဖိုင်များဖြင့် အစားထိုးပါ။ `.github` လို hidden folder ကိုပါ တင်ပါ။
3. GitHub → **Settings → Actions → General → Workflow permissions** ထဲက **Read and write permissions** ကို ဖွင့်ပါ။
4. GitHub → **Actions** tab ကိုဖွင့်ပြီး `Update hazard data` workflow ကို စမ်း run လုပ်ပါ။

## ၃။ တကယ့် flood/landslide data အတွက် လိုအပ်သည်

`data/flood_zones.geojson`, `data/landslide_zones.geojson`, `data/landslide_susceptibility.geojson` က ပထမဦးစွာ data မရှိသေးတဲ့ seed files ဖြစ်သည်။ လက်ရှိ ZIP ထဲတွင် တကယ့် hazard polygons မရှိပါ။ မမှန်တဲ့ polygon မဖန်တီးဘဲ empty အဖြစ်ထားထားသည်။

Earth Engine pipeline အတွက် Google Cloud မှ Earth Engine access ရှိတဲ့ service account JSON key လိုသည်။ ထို JSON အပြည့်အစုံကို GitHub → **Settings → Secrets and variables → Actions → New repository secret** ထဲက `EE_SERVICE_ACCOUNT_KEY` အဖြစ်သိမ်းပါ။ `EE_PROJECT` ကို repository variable အဖြစ် ထည့်နိုင်သည်။ Key ကို source code, ZIP, public repository ထဲ ဘယ်တော့မှ မထည့်ပါနှင့်။

ပြီးရင် `Actions → Update hazard data → Run workflow` ကို manually run လုပ်ပါ။ Log ထဲမှာ Earth Engine, Sentinel-1/rainfall data fetch အောင်မြင်ကြောင်း အတည်ပြုပြီးမှ hazard layer ကို ယုံကြည်ပါ။ Secret မထည့်ရသေးရင် workflow fail ဖြစ်နိုင်ပြီး flood/landslide GeoJSON မပြည့်လာပါ။

## ၄။ Live Event / Alert data အသစ်များ

`data/disaster_events.json` ကို `scripts/fetch_disaster_events.py` က update လုပ်သည်။ `Refresh live disaster events` workflow က မိနစ် ၃၀ တစ်ကြိမ် USGS/GDACS ကို စစ်ဆေးပြီး အချက်အလက်ပြောင်းလဲမှသာ commit လုပ်သည်။ USGS က ငလျင်ဖြစ်ပွားမှု GeoJSON ကိုယူပြီး GDACS public feed ကိုစစ်ဆေးသည်။ NASA FIRMS က satellite active-fire detections ကိုယူနိုင်သော်လည်း NASA Earthdata/FIRMS API key လိုသည်။ Key ရှိပါက GitHub → Settings → Secrets and variables → Actions ထဲတွင် `NASA_FIRMS_MAP_KEY` အမည်ဖြင့် သိမ်းပါ။ Key မရှိလည်း USGS/GDACS feed များကို ဆက်ယူနိုင်သည်။

မြေပုံအလွှာများထဲက `မိုးရွာသွန်းမှု Radar` ကို ဖွင့်လျှင် RainViewer ရဲ့ နောက်ဆုံး ၂ နာရီအတွင်း ရရှိနိုင်တဲ့ radar ပုံရိပ်ကို မြင်နိုင်သည်။ ဒါဟာ မိုးရွာမယ့် forecast မဟုတ်ဘဲ radar coverage က နေရာအလိုက် မတူနိုင်သည်။ RainViewer ကို data source အဖြစ် attribution ထည့်ထားသည်။

Map ရှိ အနီ/လိမ္မော် marker များသည် catalog/report/satellite detection ဖြစ်သည်။ မီးလောင်မှုတိုင်းကို မြေပြင်က အတည်ပြုပြီးသားဟု မဆိုလိုပါ။ ငလျင်ကို ကြိုတင်ခန့်မှန်းခြင်းမဟုတ်ဘဲ ဖြစ်ပွားပြီးနောက် မှတ်တမ်းကိုပြသခြင်းဖြစ်သည်။ အရေးပေါ်သတိပေးချက်အတွက် DMH နှင့် ဒေသဆိုင်ရာအာဏာပိုင်တို့ကို ဦးစားပေးပါ။

## ၅။ မိုးလေဝသနဲ့ public info

`data/public_info.json` ကို `scripts/fetch_public_info.py` က update လုပ်သည်။ GitHub Actions မှာ Internet ရရှိပြီး source endpoints တုံ့ပြန်လျှင် Open-Meteo city forecast, DMH source links, NOAA ENSO discussion, WHO emergency source links နဲ့ USGS earthquake feed ကို refresh လုပ်မည်။ လက်ရှိ seed JSON မှာ live data မပါသေးပါ။ GitHub Actions မှာ refresh အောင်မြင်/မအောင်မြင်ကို `source_checks` နဲ့ Last updated အချိန်များကို စစ်ဆေးပါ။

ဒီ weather threshold များက app ၏ ကိုယ်ပိုင် screening စည်းမျဉ်းများသာ ဖြစ်ပြီး DMH official warning မဟုတ်ပါ။ WHO လင့်ခ်တွေကလည်း မြန်မာနိုင်ငံမှာ outbreak ဖြစ်နေပြီဆိုတဲ့ အတည်ပြုချက်မဟုတ်ပါ။ အရေးပေါ်အခြေအနေမှာ မူရင်း DMH/ဒေသဆိုင်ရာ အာဏာပိုင်တို့ရဲ့ နောက်ဆုံးကြေညာချက်ကို ဦးစားပေးပါ။

## ၆။ စစ်ဆေးထားသောအပိုင်းနှင့် ကန့်သတ်ချက်

Project တွင် Python offline self-tests, JavaScript syntax checks, JSON ဖိုင်စစ်ဆေးမှု၊ GitHub Actions YAML စစ်ဆေးမှုနဲ့ demo build စမ်းသပ်မှု အောင်မြင်ထားသည်။ ဒီစမ်းသပ်မှုတွေက live internet API သို့မဟုတ် Earth Engine credentials အလုပ်လုပ်ကြောင်း အတည်မပြုပါ။ ဒီ environment မှာ live API ကို အဆုံးထိ ချိတ်ဆက်စမ်းသပ်မထားနိုင်ပါ။

### Live Alerts မှာ ထပ်ပါလာမယ့် Forecast Screening

`Refresh live disaster events` workflow က USGS ငလျင်၊ GDACS သတိပေးချက်များအပြင် Open-Meteo ရဲ့ ၃ ရက်စာခန့်မှန်းချက်ကို မြန်မာနိုင်ငံရှိ မြို့ ၂၀ အတွက် စစ်ဆေးပြီး မိုးသည်းထန်နိုင်ခြေ၊ လေပြင်း၊ အပူလွန်ကဲမှုနဲ့ UV အညွှန်းမြင့်မားမှုတို့ကို မြေပုံနဲ့ Alert စာရင်းမှာ ပြနိုင်ပါတယ်။ သတ်မှတ်ထားတဲ့ threshold တွေဟာ app ရဲ့ screening rule သာဖြစ်ပြီး DMH ရဲ့ တရားဝင် warning မဟုတ်ပါ။ မိုးရွာမယ်ဆိုတာက ရေကြီးမယ်လို့ အတည်ပြုတာ မဟုတ်ပါ။

ဒေတာအသစ်ကို တကယ်ရဖို့ repository ထဲက **Actions → Refresh live disaster events → Run workflow** ကို တစ်ကြိမ် run လုပ်ပြီး workflow အောင်မြင်/မအောင်မြင်ကို စစ်ပါ။ GitHub Actions ပိတ်ထားရင် ဖိုင်ထဲက seed data ကိုယ်တိုင် live မဖြစ်ပါ။

## ၇။ မြို့နယ်အလိုက် မိုးရေချိန်ခန့်မှန်းချက် (အသစ်)

`scripts/fetch_rain_forecast.py` က မြို့နယ် ၃၃၀ ရဲ့ ဗဟိုနေရာတိုင်းအတွက် လွန်ခဲ့သော နာရီ ၇၂ နှင့် နောက်နာရီ ၇၂ အတွင်း မိုးရေချိန်ကို Open-Meteo မှ ယူပြီး `data/rain_forecast.json` ကို ရေးသည်။ မြေပုံပေါ်တွင် မြို့နယ်ကို အဝါ (သတိထားရန်)၊ လိမ္မော် (သတိပေး)၊ အနီ (အလွန်အန္တရာယ်) ဖြင့် ဆိုးပြသည်။

အဆင့်သတ်မှတ်ပုံက အကြမ်းဖျင်းစည်းမျဉ်း ဖြစ်သည်။ ၂၄ နာရီအတွင်း အများဆုံးမိုးကို အိန္ဒိယမိုးလေဝသဌာန၏ အဆင့်များ (၆၄.၅ / ၁၁၅.၆ / ၂၀၄.၅ မမ) နှင့်ယှဉ်ပြီး၊ ၇၂ နာရီအတွင်း ၁၅၀ မမနှင့်အထက် ရွာပြီးသားဆိုလျှင် တစ်ဆင့်၊ ရေကြီးဖူးသောဧရိယာ ၁၅% နှင့်အထက်ဆိုလျှင် တစ်ဆင့် ထပ်မြှင့်သည်။ **ဤစည်းမျဉ်းများကို အရင်ရေကြီးမှုများနှင့် မတိုက်စစ်ရသေးပါ။ တရားဝင်သတိပေးချက် မဟုတ်ပါ။**

Live Alerts ထဲက မြို့ ၂၀ အတွက် forecast screening နှင့် ဤမြို့နယ်အလွှာတို့သည် Open-Meteo ကို သုံးကြသော်လည်း အလွှာနှစ်ခုဖြစ်ပြီး တစ်ခုနှင့်တစ်ခု မရောပါ။ `update_data.yml` က တစ်နေ့ ၂ ကြိမ် run သဖြင့် မြို့နယ်မိုးရေချိန်ခန့်မှန်းချက်သည် နာရီအလိုက် အချိန်နှင့်တပြေးညီ မဟုတ်ပါ။ ပိုခဏခဏလိုလျှင် workflow ထဲက `cron` ကို ပြောင်းပါ။

```bash
python scripts/fetch_rain_forecast.py --selftest   # အင်တာနက်မလို
python scripts/fetch_rain_forecast.py              # အင်တာနက်လို၊ data/rain_forecast.json ကို ရေးသည်
python scripts/make_simple_map_data.py             # ဖိုင်အဖြစ် ဖွင့်ရင်လည်း မြင်ချင်လျှင်
```

## ၈။ weather website ၏ ဒေတာကို ဤမြေပုံတွင် ပြန်သုံးခြင်း (အသစ်)

`scripts/import_weather_site_data.py` က မင်း၏ weather website (myanmar-weather) ထဲက ဒေတာကို ယူသည်။

| ဒေတာ | ဖိုင် | မြေပုံပေါ်တွင် |
|---|---|---|
| DMH ရေမျက်နှာပြင်တိုင်းတာရေးစခန်း ၄၇ ခု | `data/ref/dmh_river_stations.json` | မြစ်ရေခန့်မှန်းချက်အစက်များ (အရင် ကျွန်တော်ခန့်မှန်းထားသော နေရာ ၂၀ အစား) |
| ဆေးရုံ ၁,၁၃၆ ခု (MIMU/CDE ၂၀၂၀၊ CC BY 4.0) | `data/hospitals.geojson` | အလွှာတစ်ခု (ပုံမှန်ပိတ်ထား)။ အချိန်နှင့်တပြေးညီ မဟုတ်ပါ |
| DMH တရားဝင်သတိပေးချက်များ | `data/official_alerts.json` | Live panel ထဲက စာရင်းနှင့် သတိပေးထားသော တိုင်း/ပြည်နယ်ကို အရောင်ပြခြင်း |

တစ်ကြိမ်သာ (ဖိုင်တွဲနှစ်ခု ကွန်ပျူတာထဲမှာ ရှိလျှင်):

```bash
python scripts/import_weather_site_data.py --weather-dir ../myanmar-weather-v6_16_2
python scripts/make_simple_map_data.py
```

DMH သတိပေးချက်ကို အမြဲ update လုပ်လိုလျှင် weather website ကို အင်တာနက်ပေါ် တင်ထားပြီး GitHub repository ၏ Settings → Secrets and variables → Actions → Variables ထဲ `WEATHER_API_BASE` (ဥပမာ `https://your-weather-site.example`) ထည့်ပါ။ workflow က `/api/dmh/alerts` ကို ခေါ်ယူမည်။ ထည့်မထားလျှင် ဤအဆင့်ကို ကျော်သည်။

**သတိပြုရန်။** weather website ၏ `risk_engine/data/official_alerts_state.json` အရ DMH မှ ရယူမှု အောင်မြင်ခဲ့ဖူးခြင်း မရှိ (HTTP error ၇ ကြိမ်)။ ထို့ကြောင့် `official_alerts.json` သည် အလွတ်ဖြစ်ပြီး မြေပုံက "DMH မှ ရယူမှု မအောင်မြင်သေးပါ" ဟု ပြသည်။ သတိပေးချက်မရှိခြင်းသည် DMH မထုတ်ပြန်ခြင်းကို မဆိုလိုပါ။

## ၉။ ဒီဇိုင်းအသစ် (စိတ်အေးအေးနဲ့ အသေးစိတ်ကြည့်နိုင်ရန်)

- **ပထမဆုံးဝင်ရင် "မြေပုံကို ဘယ်လိုဖတ်မလဲ" ရှင်းလင်းချက်** တစ်ခု ပေါ်ပါမည်။ တစ်ကြိမ်ဖတ်ပြီးရင် ထပ်မပေါ်ပါ။ အလွှာပြတင်းပေါက်ထဲက "မြေပုံကို ဘယ်လိုဖတ်မလဲ" ကိုနှိပ်ပြီး ပြန်ကြည့်နိုင်သည်။
- **အလွှာတွေကို အုပ်စုခွဲထားသည်။** (ယခုအခြေအနေနှင့် ခန့်မှန်းချက်၊ ဂြိုဟ်တုဖြင့်တွက်ချက်ထားသည်၊ နောက်ခံအချက်အလက်၊ နယ်နိမိတ်)။ "အကျဉ်းချုပ် / ရေကြီးမှု / တောင်ပြို / နယ်နိမိတ်သာ" ခလုတ်တွေနဲ့ တစ်ချက်နှိပ်ရုံ ပြောင်းလို့ရသည်။
- **အရောင်ကို အနီအစွမ်းမသုံးတော့ပါ။** အဝါ (သတိထားရန်)၊ လိမ္မော် (သတိပြုရန်)၊ အုတ်နီရောင် (အထူးသတိပြုရန်) ဖြစ်သည်။ မျက်စိမှိတ်တုတ်လင်းတာ၊ အနီရောင်အော်ဒါ မပါတော့ပါ။
- **မြို့နယ်၊ မြစ်စခန်းကို နှိပ်ရင် "အဓိပ္ပာယ်" စာကြောင်း** ပါသည်။ (ဥပမာ - "မိုးသည်းနိုင်ပါသည်။ ရာသီဥတုသတင်းကို ဆက်လက်စောင့်ကြည့်ပါ")။
- **အညွှန်း (legend)** သည် ဖွင့်ထားသော အလွှာများကိုသာ ပြသည်။
- ဒေတာ မရှိသေးခင် မြေပုံအလွတ်မဖြစ်စေရန် ရေကြီးဖူးသောနေရာကို အလိုအလျောက် ပြထားသည်။
- အရောင်သာမက စာသားနဲ့လည်း အဆင့်ကို ပြထားသည်။ လှုပ်ရှားမှုလျှော့ထားလိုသူများအတွက် animation ကို ပိတ်ပေးသည်။
