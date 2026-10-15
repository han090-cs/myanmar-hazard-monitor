/* Myanmar Hazard Monitor - source-attributed multi-hazard front end (Leaflet) */
(function () {
  'use strict';

  // ------------------------------------------------------------------ configuration
  var CONFIG = {
    // Branch that holds data/ (use the DATA_BRANCH repository variable's value, e.g. "data", if you set one)
    branch: 'main',
    // Folder inside that branch. For a DATA_BRANCH the files sit at the branch root: set this to ''.
    dataPath: 'data',
    // Optional overrides. Normally owner/repo are detected from the github.io URL.
    owner: null,
    repo: null,
    files: {
      flood: 'flood_zones.geojson',
      landslide: 'landslide_zones.geojson',
      summary: 'summary.json',
      metadata: 'metadata.json',
      susceptibility: 'landslide_susceptibility.geojson',
      river: 'river_forecast.json',
      rain: 'rain_forecast.json',
      hospitals: 'hospitals.geojson',
      officialAlerts: 'official_alerts.json',
      floodprone: 'flood_prone.geojson',
      proneStats: 'flood_prone_stats.json',
      publicInfo: 'public_info.json',
      events: 'disaster_events.json',
      outline: 'ref/myanmar_outline.geojson',
      admin1: 'ref/admin1_mmr.geojson',
      admin3: 'ref/admin3_mmr.geojson'
    },
    bounds: [[9.6, 92.1], [28.6, 101.2]],
    maxBounds: [[7.5, 90.0], [30.5, 103.5]],
    proneColors: { 3: '#007f73', 2: '#2bb3a3', 1: '#9fe0d6' },
    proneFillOpacity: 0.5,
    rainColors: { 1: '#f2d16b', 2: '#e8953a', 3: '#bf4a36' },
    staleSatelliteHours: 72,
    refreshMinutes: 20,
    floodColor: '#0077be',
    floodBorder: '#00507f',
    floodFillOpacity: 0.55,
    slideColors: { 3: '#b8402f', 2: '#e08e45', 1: '#e9c46a' },
    slideFillOpacity: 0.6,
    suscColors: { 3: '#5a189a', 2: '#9d4edd', 1: '#cdb4db' },
    suscFillOpacity: 0.35,
    riverColors: { 0: '#2a9d8f', 1: '#f2d16b', 2: '#e8953a', 3: '#bf4a36' },
    riverUnknown: '#8d99ae'
  };

  // ------------------------------------------------------------------ i18n
  var I18N = {
    my: {
      title: 'မြန်မာနိုင်ငံ သဘာဝဘေးအန္တရာယ် စောင့်ကြည့်ရေး',
      subtitle: 'မြေပုံ၊ ခန့်မှန်းချက်၊ ဖြစ်ပွားမှုနှင့် တရားဝင်သတိပေးချက်များ',
      cardFlood: 'စုစုပေါင်း ရေမြုပ်ဧရိယာ (Hectares)',
      cardSlide: 'တောင်ပြိုသတိပေးမြို့နယ် အရေအတွက်',
      cardTime: 'နောက်ဆုံး ဂြိုဟ်တုဒေတာ ရရှိချိန်',
      liveAlertsTitle: 'Live သတိပေးချက်များ',
      liveAlertsNote: 'အောက်ပါအချက်အလက်များသည် ရင်းမြစ်အလိုက် observation/alert ဖြစ်ပြီး အန္တရာယ်အားလုံးကို မဖုံးလွှမ်းနိုင်ပါ။',
      eventsLayer: 'ငလျင် / ဘေးအန္တရာယ် ဖြစ်ပွားမှုများ',
      eventsUpdated: 'ဖြစ်ပွားမှုဒေတာ နောက်ဆုံးရရှိချိန်',
      radarLayer: 'မိုးရွာသွန်းမှု Radar (နောက်ဆုံး ၂ နာရီ)',
      radarStatus: 'Radar ပုံရိပ်',
      radarUnavailable: 'Radar ဒေတာ မရရှိသေးပါ။ ဒေသအလိုက် coverage မတူနိုင်ပါ။',
      eventsEmpty: 'လက်ရှိဒေတာဖိုင်တွင် event မရှိပါ။ ဒါဟာ အန္တရာယ်မရှိကြောင်း သက်သေမဟုတ်ပါ။',
      eventEarthquake: 'ငလျင်', eventFire: 'ဂြိုဟ်တု မီးလောင်မှုတွေ့ရှိချက်', eventAlert: 'ဘေးအန္တရာယ် သတိပေးချက်',
      eventMagnitude: 'ပြင်းအား', eventDepth: 'အနက်', eventSource: 'ရင်းမြစ်', eventStatus: 'အမျိုးအစား',
      layers: 'အလွှာများ',
      floodLayer: 'ရေကြီးမြုပ်နှံမှု',
      slideLayer: 'တောင်ပြိုအန္တရာယ်',
      opacity: 'အလွှာ ထင်ရှားမှု (Opacity)',
      basemap: 'မြေပုံနောက်ခံ',
      bmHot: 'OSM Humanitarian (HOT)',
      bmOsm: 'OpenStreetMap ပုံမှန်',
      bmSat: 'ဂြိုဟ်တုဓာတ်ပုံ + OSM အမည်များ',
      locate: 'ကျွန်ုပ်၏တည်နေရာ',
      topAffected: 'ထိခိုက်မှုအများဆုံး မြို့နယ်များ',
      dataDetails: 'ဒေတာ အသေးစိတ်',
      legend: 'အညွှန်း',
      legFlood: 'ရေကြီးမြုပ်နှံသည့်နေရာ',
      legHigh: 'တောင်ပြိုအန္တရာယ် မြင့်',
      legMod: 'တောင်ပြိုအန္တရာယ် အလယ်အလတ်',
      legLow: 'တောင်ပြိုအန္တရာယ် နိမ့်',
      loading: 'ဒေတာ ရယူနေပါသည်',
      close: 'ပိတ်ရန်',
      focusMap: 'မြေပုံသာ ပြရန်',
      mapLabel: 'မြန်မာနိုင်ငံ ရေကြီးမှုနှင့် တောင်ပြိုမှု မြေပုံ',
      disclaimer: 'ဤအချက်အလက်များသည် ဂြိုဟ်တုဒေတာအပေါ် အခြေခံသော ခန့်မှန်းချက်များသာဖြစ်ပြီး တရားဝင်သတိပေးချက်များကို အစားထိုးခြင်းမရှိပါ။ မိုးလေဝသနှင့် ဇလဗေဒညွှန်ကြားမှုဦးစီးဌာန (DMH) နှင့် ဒေသဆိုင်ရာ အာဏာပိုင်များ၏ ညွှန်ကြားချက်ကို လိုက်နာပါ။',
      noData: 'ဒေတာ မရရှိသေးပါ',
      polygons: 'နေရာ {n} ခု',
      townshipsAffected: 'ထိခိုက်မြို့နယ် {n} ခု',
      high: 'မြင့်',
      moderate: 'အလယ်အလတ်',
      low: 'နိမ့်',
      warnBreakdown: 'မြင့် {h} · အလယ်အလတ် {m}',
      sensorLine: 'Sentinel-1 ရေဒါ',
      ago: '{t} ခန့်က',
      hours: '{n} နာရီ',
      minutes: '{n} မိနစ်',
      days: '{n} ရက်',
      township: 'မြို့နယ်',
      district: 'ခရိုင်',
      region: 'တိုင်း/ပြည်နယ်',
      area: 'ခန့်မှန်းဧရိယာ',
      ha: 'ဟက်တာ',
      hazardLevel: 'အန္တရာယ်အဆင့်',
      floodPopup: 'ရေကြီးမြုပ်နှံသည့်နေရာ',
      slidePopup: 'တောင်ပြိုအန္တရာယ်',
      dEmpty: 'မရှိသေးပါ',
      dSatellite: 'ဂြိုဟ်တုဒေတာ',
      dWindow: 'ပေါင်းစပ်ကာလ',
      dBaseline: 'ခြောက်သွေ့ရာသီ အခြေခံ',
      dChecked: 'နောက်ဆုံးစစ်ဆေးချိန်',
      dRain: 'မိုးရေချိန်ရင်းမြစ်',
      dRainEnd: 'မိုးရေချိန် ကာလအဆုံး',
      dRainMax: '၇ ရက် မိုးရေချိန် အများဆုံး',
      dRun: 'Pipeline အခြေအနေ',
      mm: 'မီလီမီတာ',
      bannerDemo: 'စမ်းသပ်ပြသမှုသာ (DEMO) – ဤဒေတာများသည် ဥပမာအတု ဖြစ်ပြီး တကယ့်ရေကြီးမှု/တောင်ပြိုမှု မဟုတ်ပါ။',
      bannerNone: 'Pipeline မှ ဒေတာ မထုတ်ရသေးပါ။ GitHub Actions ကို ပထမဆုံးအကြိမ် run ပြီးမှ မြေပုံတွင် ဒေတာပေါ်ပါမည်။',
      bannerStale: 'ဂြိုဟ်တုဒေတာ {t} ရှိပြီ ဖြစ်သောကြောင့် ရေကြီးမှုအလွှာ ဟောင်းနေနိုင်ပါသည်။',
      bannerRain: 'မိုးရေချိန်ဒေတာ {t} ရှိပြီ ဖြစ်၍ တောင်ပြိုအလွှာ နောက်ကျနေနိုင်ပါသည်။',
      bannerError: 'နောက်ဆုံး pipeline run တွင် အမှားရှိခဲ့ပါသည်။ ယခင်ဒေတာကို ဆက်ပြထားပါသည်။',
      bannerLoad: 'ဒေတာ ရယူ၍ မရပါ။ အင်တာနက်ကို စစ်ဆေးပြီး ထပ်ကြိုးစားပါ။',
      retry: 'ထပ်ကြိုးစားရန်',
      locateFail: 'တည်နေရာ ရှာမတွေ့ပါ',
      status_ok: 'ပုံမှန်',
      status_partial: 'တစ်စိတ်တစ်ပိုင်း',
      status_error: 'အမှားရှိ',
      status_never_run: 'မ run ရသေးပါ',
      cardRiver: 'မြစ်ရေကြီးမှု သတိပေးနေရာ (ရက် ၃၀ ခန့်မှန်း)',
      riverSub: 'စောင့်ကြည့်သောမြစ်နေရာ {n} ခု',
      riverLayer: 'မြစ်ရေကြီးမှု ခန့်မှန်းချက်',
      suscLayer: 'တောင်ပြိုနိုင်ချေရှိသော မြေမျက်နှာပြင် (ကုန်းစောက်)',
      legSusc: 'မြေမျက်နှာပြင် စောက်ကြီးသည့်နေရာ',
      legRiver0: 'မြစ်ရေ ပုံမှန်',
      legRiver1: 'မြစ်ရေ မြင့်လာ',
      legRiver2: 'မြစ်ရေ ကြီး',
      legRiver3: 'မြစ်ရေ အလွန်ကြီး',
      riverPopup: 'မြစ်ရေကြီးမှု ခန့်မှန်းချက်',
      suscPopup: 'ကုန်းစောက်ကြီးသော မြေမျက်နှာပြင်',
      slopeLevel: 'စောက်ဆင်ရည်အဆင့်',
      riverName: 'မြစ်',
      level: 'အဆင့်',
      level0: 'ပုံမှန်',
      level1: 'မြင့်လာ',
      level2: 'ကြီး',
      level3: 'အလွန်ကြီး',
      levelNone: 'အဆင့်သတ်မှတ်ချက်မရှိ',
      nowQ: 'ယခု ရေစီးအား',
      peakQ: 'ရက် ၃၀ အတွင်း အမြင့်ဆုံး',
      peakOn: 'အမြင့်ဆုံးရက်',
      thrLine: 'တိုင်းတာအဆင့် (၂/၅/၂၀ နှစ်): {a} / {b} / {c}',
      riverNote: 'GloFAS မြစ်ရေစီးအား ခန့်မှန်းချက်သာ ဖြစ်ပြီး ရေလျှံမည့်နယ်မြေကို မပြပါ။ မြစ်ငယ်၊ မြို့တွင်းရေကြီးမှုများ မပါဝင်ပါ။',
      m3s: 'မီတာ³/စက္ကန့်',
      dRiverGen: 'မြစ်ခန့်မှန်းချက် ထုတ်ချိန်',
      suscNote: 'ကုန်းစောက် (SRTM) အခြေခံသာ ဖြစ်ပြီး NASA LHASA မဟုတ်ပါ။ မိုးရွာသည့်အခါ အန္တရာယ်ပိုမြင့်နိုင်သည့် နေရာများကို ညွှန်ပြသည်။',
      proneLayer: 'ရေကြီးဖူးသော နေရာများ (အတိတ်ဒေတာ)',
      legProne: 'ရေကြီးဖူးသောနေရာ (အတိတ်ဒေတာ)',
      pronePopup: 'ရေကြီးဖူးသော နေရာ',
      proneClass: 'ရေကြီးဖူးသည့် အကြိမ်',
      Once: 'တစ်ကြိမ်',
      'Several times': 'အကြိမ်အနည်းငယ်',
      Often: 'မကြာခဏ',
      proneNote: 'ပေးထားသော ဒေတာဖိုင်အရ မီတာ ၂၅၀ ကွက်များဖြစ်သည်။ ဒေတာရင်းမြစ်နှင့် ရက်စွဲ မသိရပါ။ ကွက်တစ်ခု ထပ်ခါထပ်ခါပါသည့် အကြိမ်ကို ရေကြီးခဲ့သည့်အကြိမ်အဖြစ် ယူဆထားသည် (အတည်မပြုရသေးပါ)။',
      sharePct: 'မြို့နယ်ထဲက အချိုး',
      boundStates: 'တိုင်းဒေသကြီး/ပြည်နယ် နယ်နိမိတ်',
      boundTowns: 'မြို့နယ် နယ်နိမိတ်',
      groupNow: 'ယခုအခြေအနေနှင့် ခန့်မှန်းချက်',
      groupSat: 'ဂြိုဟ်တုဖြင့် တွက်ချက်ထားသည်',
      groupBase: 'နောက်ခံ အချက်အလက် (အတိတ်/ပုံသေ)',
      groupBounds: 'နယ်နိမိတ်',
      presetsTitle: 'မြင်ကွင်း အမြန်ရွေးရန်',
      presetSummary: 'အကျဉ်းချုပ်',
      presetFlood: 'ရေကြီးမှု',
      presetSlide: 'တောင်ပြို',
      presetClear: 'နယ်နိမိတ်သာ',
      helpBtn: 'မြေပုံကို ဘယ်လိုဖတ်မလဲ',
      introTitle: 'မြေပုံကို ဘယ်လိုဖတ်မလဲ',
      introLead: 'ဒီမြေပုံက ကြိုတင်ဂရုစိုက်နိုင်ရန် အချက်အလက်တွေကို စုပေါင်းပြထားတာပါ။ စိတ်လှုပ်ရှားစရာ မလိုပါ၊ တစ်ဆင့်ချင်း ကြည့်နိုင်ပါတယ်။',
      intro1: 'အရောင်က အဆင့်ကို ပြတာပါ။ အဝါ = သတိထားရန်၊ လိမ္မော် = သတိပြုရန်၊ အုတ်နီရောင် = အထူးသတိပြုရန်။ အရောင်မပါရင် အထူးသတိပေးစရာ မတွေ့သေးဟု ဆိုလိုပါတယ်။',
      intro2: 'မြေပုံပေါ် နေရာတစ်ခုကို နှိပ်ရင် အသေးစိတ်နဲ့ အဓိပ္ပာယ်ကို ဖတ်နိုင်ပါတယ်။',
      intro3: 'ခန့်မှန်းချက်တွေက ကွန်ပျူတာ တွက်ချက်ထားတာ ဖြစ်ပြီး တရားဝင်သတိပေးချက် မဟုတ်ပါ။ DMH နဲ့ ဒေသအာဏာပိုင်ရဲ့ ကြေညာချက်ကို အမြဲ ဦးစားပေးပါ။',
      intro4: 'ဒေတာ မပေါ်သေးတာ၊ ရယူမှု မအောင်မြင်တာက "အန္တရာယ်မရှိဘူး" လို့ မဆိုလိုပါ။ မသေချာရင် တရားဝင်ရင်းမြစ်ကို တိုက်ရိုက်ကြည့်ပါ။',
      introOk: 'နားလည်ပါပြီ',
      rainMean0: 'ယခုခန့်မှန်းချက်အရ မိုးအထူးသည်းမည့် လက္ခဏာ မတွေ့ပါ။',
      rainMean1: 'မိုးသည်းနိုင်ပါသည်။ ရာသီဥတုသတင်းကို ဆက်လက်စောင့်ကြည့်ပါ။',
      rainMean2: 'မိုးအလွန်သည်းနိုင်ပါသည်။ နိမ့်သောနေရာနှင့် မြစ်ချောင်းအနီးရှိသူများ ကြိုတင်ပြင်ဆင်ထားသင့်ပါသည်။',
      rainMean3: 'မိုးထူးခြားစွာ သည်းနိုင်ပါသည်။ DMH နှင့် ဒေသအာဏာပိုင် ကြေညာချက်ကို ချက်ချင်း စစ်ဆေးပြီး လိုက်နာပါ။',
      riverMean0: 'မြစ်ရေစီးအား ပုံမှန်အတိုင်း ခန့်မှန်းထားသည်။',
      riverMean1: 'မြစ်ရေစီးအား ပုံမှန်ထက် မြင့်လာနိုင်သည်။ ဆက်လက်စောင့်ကြည့်ပါ။',
      riverMean2: 'မြစ်ရေစီးအား အတော်မြင့်နိုင်သည်။ မြစ်ကမ်းနားရှိသူများ ကြိုတင်ပြင်ဆင်ထားပါ။',
      riverMean3: 'မြစ်ရေစီးအား ထူးခြားစွာ မြင့်နိုင်သည်။ DMH နှင့် ဒေသအာဏာပိုင် ကြေညာချက်ကို ချက်ချင်း စစ်ဆေးပါ။',
      meaningLabel: 'အဓိပ္ပာယ်',
      hospitalsLayer: 'ဆေးရုံများ (MIMU/CDE ၂၀၂၀)',
      legHospital: 'ဆေးရုံ (၂၀၂၀ ဒေတာ)',
      hospPopup: 'ဆေးရုံ',
      hospLevel: 'အမျိုးအစား',
      hospBeds: 'ကုတင်အရေအတွက်',
      hospTownship: 'မြို့နယ်',
      hospConf: 'တည်နေရာ တိကျမှု',
      hospConfLow: 'မတိကျနိုင် (ခန့်မှန်းတည်နေရာ)',
      hospConfOk: 'တိကျသည်ဟု သတ်မှတ်ထား',
      hospNote: 'MIMU/CDE-Myanmar ၂၀၂၀ ဒေတာ (CC BY 4.0) ဖြစ်ပြီး အချိန်နှင့်တပြေးညီ မဟုတ်ပါ။ ဆေးရုံ၏ လက်ရှိအခြေအနေ (ရေကြီးနေခြင်း၊ ပိတ်ထားခြင်း) ကို မပြပါ။',
      dmhLayer: 'DMH သတိပေးထားသော တိုင်း/ပြည်နယ်',
      legDmh: 'DMH သတိပေးထားသော တိုင်း/ပြည်နယ်',
      dmhAlertsTitle: 'DMH တရားဝင် သတိပေးချက်များ',
      dmhNone: 'ယခု သက်တမ်းရှိသော DMH သတိပေးချက် မတွေ့ပါ။',
      dmhNoData: 'DMH ဒေတာ မရရှိသေးပါ။',
      dmhLastOk: 'နောက်ဆုံး အောင်မြင်စွာ ရယူချိန်',
      dmhNeverOk: 'DMH မှ ရယူမှု တစ်ကြိမ်မျှ မအောင်မြင်သေးပါ။',
      dmhErrorNote: 'နောက်ဆုံး ရယူရာတွင် အမှားရှိခဲ့သည်။ သတိပေးချက်မတွေ့ခြင်းသည် DMH က မထုတ်ပြန်ခြင်းကို မဆိုလိုပါ။ DMH ဝက်ဘ်ဆိုက်ကို တိုက်ရိုက်ကြည့်ပါ။',
      dmhActive: 'သက်တမ်းရှိ',
      dmhEnded: 'သက်တမ်းကုန်',
      dmhValid: 'သက်တမ်း',
      dmhRegions: 'ဒေသများ',
      dmhOpen: 'DMH မူရင်းစာမျက်နှာ',
      dmhType_heavy_rain: 'မိုးသည်းထန်စွာ ရွာသွန်မည့် သတိပေးချက်',
      dmhType_cyclone: 'ဆိုင်ကလုန်း သတိပေးချက်',
      dmhType_depression: 'ဖိအားနိမ့်ဒေသ သတိပေးချက်',
      dmhType_strong_wind: 'လေပြင်း သတိပေးချက်',
      dmhType_untimely_rain: 'အချိန်မတန်မိုး သတိပေးချက်',
      dmhType_flood: 'ရေကြီးမှု သတိပေးချက်',
      dmhType_tsunami: 'ဆူနာမီ သတိပေးချက်',
      dmhType_weather_early_warning: 'မိုးလေဝသ ကြိုတင်သတိပေးချက်',
      dmhType_other: 'DMH သတိပေးချက်',
      riverDmhStation: 'DMH ရေမျက်နှာပြင် တိုင်းတာရေးစခန်း',
      eventsSubTitle: 'ငလျင်နှင့် အခြား ဖြစ်ရပ်များ',
      rainLayer: 'မိုးရေချိန် ခန့်မှန်းချက် (မြို့နယ်၊ နာရီ ၇၂)',
      legRain1: 'မိုးရေ သတိထားရန်',
      legRain2: 'မိုးရေ သတိပြုရန်',
      legRain3: 'မိုးရေ အထူးသတိပြုရန်',
      rainPopup: 'မိုးရေချိန် ခန့်မှန်းချက်',
      rainLevel: 'သတိပေးအဆင့်',
      rl0: 'ပုံမှန်',
      rl1: 'သတိထားရန်',
      rl2: 'သတိပြုရန်',
      rl3: 'အထူးသတိပြုရန်',
      rainPast72: 'လွန်ခဲ့သော နာရီ ၇၂ က ရွာပြီး',
      rainNext24: 'နောက် နာရီ ၂၄',
      rainNext72: 'နောက် နာရီ ၇၂',
      rainMax24: 'အများဆုံး ၂၄ နာရီ',
      rainProne: 'ရေကြီးဖူးသော ဧရိယာ အချိုး',
      rainWhyWet: 'မြေစိုနေပြီး (၇၂ နာရီ ၁၅၀ မမ နှင့်အထက်) ဖြစ်၍ တစ်ဆင့်မြှင့်ထားသည်',
      rainWhyProne: 'ရေကြီးဖူးသော ဧရိယာ ၁၅% နှင့်အထက် ဖြစ်၍ တစ်ဆင့်မြှင့်ထားသည်',
      rainNote: 'မြို့နယ်ဗဟိုနေရာ၏ မိုးရေချိန်ခန့်မှန်းချက်သာ ဖြစ်သည်။ အဆင့်သည် အကြမ်းဖျင်းစည်းမျဉ်း (အိန္ဒိယမိုးဇာတ်ကြောင်း ၂၄ နာရီ အဆင့်များ) ဖြစ်ပြီး အရင်ရေကြီးမှုများနှင့် တိုက်စစ်မထားပါ။ တရားဝင်သတိပေးချက် မဟုတ်ပါ။ DMH ကြေညာချက်ကို လိုက်နာပါ။',
      mm: 'မမ',
      topRainTitle: 'မိုးအများဆုံး ခန့်မှန်းရသည့် မြို့နယ်များ (နာရီ ၇၂)',
      dRainGen: 'မိုးရေချိန်ခန့်မှန်းချက် ထုတ်ချိန်',
      publicInfoTitle: 'ရာသီဥတုနှင့် အများပြည်သူ သတင်းအချက်အလက်',
      publicInfoIntro: 'မြို့ကြီးများ၏ ၇ ရက် ခန့်မှန်းချက်၊ El Niño အခြေအနေနှင့် အတည်ပြုနိုင်သော ရင်းမြစ်များ။',
      nextDays: '၇ ရက်စာ ခန့်မှန်းချက် ကြည့်ရန်',
      publicDisclaimer: 'ခန့်မှန်းအခြေပြု စစ်ဆေးမှုသာဖြစ်ပြီး တရားဝင်သတိပေးချက် မဟုတ်ပါ။ မူရင်း DMH/WHO/NOAA/USGS အချက်အလက်ကို အတည်ပြုပါ။',
      dmhTitle: 'DMH တရားဝင် မိုးလေဝသသတင်း',
      healthTitle: 'WHO ကျန်းမာရေးသတင်းရင်းမြစ်',
      healthNote: 'WHO ခေါင်းစဉ်များသည် မြန်မာနိုင်ငံအတွင်း အတည်ပြုထားသော ရောဂါဖြစ်ပွားမှုစာရင်း မဟုတ်ပါ။ မူရင်းကြေညာချက်ကို စစ်ဆေးပါ။',
      quakeTitle: 'မကြာသေးမီက ငလျင်များ',
      publicUnavailable: 'ဤဒေတာကို မရရှိသေးပါ။ မူရင်းရင်းမြစ်ကို ဖွင့်ကြည့်ပါ။',
      sourceUpdated: 'ဒေတာစစ်ဆေးချိန်',
      dayTemp: 'အမြင့်ဆုံးအပူချိန်',
      dayRain: 'ခန့်မှန်းမိုးရေချိန်',
      dayUV: 'UV အညွှန်း',
      heatRisk: 'အပူဒဏ် အန္တရာယ်',
      uvRisk: 'ခရမ်းလွန်ရောင်ခြည်',
      rainRisk: 'မိုးများနိုင်မှု',
      windRisk: 'လေပြင်းအန္တရာယ်',
      risk_moderate: 'သတိထား',
      risk_high: 'မြင့်',
      risk_severe: 'အလွန်မြင့်',
      ensoStatus: 'NOAA ENSO အခြေအနေ',
      issued: 'ထုတ်ပြန်ရက်',
      earthquakeMagnitude: 'ပြင်းအား',
      earthquakeTime: 'ဖြစ်ပွားချိန်',
      noBulletins: 'ဤအချိန်တွင် ထုတ်ယူနိုင်သော ခေါင်းစဉ် မတွေ့ပါ။ မူရင်းစာမျက်နှာကို ကြည့်ပါ။'
    },
    en: {
      title: 'Myanmar Hazard Monitor',
      subtitle: 'Map, forecasts, observed events and official alerts',
      cardFlood: 'Total flooded area (hectares)',
      cardSlide: 'Townships under landslide warning',
      cardTime: 'Latest satellite data acquired',
      liveAlertsTitle: 'Live alerts',
      liveAlertsNote: 'These are source-reported observations/alerts and may not cover every hazard.',
      eventsLayer: 'Earthquakes / reported hazard events',
      eventsUpdated: 'Latest event data',
      radarLayer: 'Rain radar (past 2 hours)',
      radarStatus: 'Radar imagery',
      radarUnavailable: 'Radar data unavailable. Coverage varies by location.',
      eventsEmpty: 'No events in the current data file. This does not prove that no hazard exists.',
      eventEarthquake: 'Earthquake', eventFire: 'Satellite fire detection', eventAlert: 'Disaster alert',
      eventMagnitude: 'Magnitude', eventDepth: 'Depth', eventSource: 'Source', eventStatus: 'Type',
      layers: 'Layers',
      floodLayer: 'Flood inundation',
      slideLayer: 'Landslide hazard',
      opacity: 'Layer opacity',
      basemap: 'Base map',
      bmHot: 'OSM Humanitarian (HOT)',
      bmOsm: 'OpenStreetMap standard',
      bmSat: 'Satellite imagery + OSM labels',
      locate: 'My location',
      topAffected: 'Most affected townships',
      dataDetails: 'Data details',
      legend: 'Legend',
      legFlood: 'Flooded area',
      legHigh: 'Landslide hazard: high',
      legMod: 'Landslide hazard: moderate',
      legLow: 'Landslide hazard: low',
      loading: 'Loading data',
      close: 'Close',
      focusMap: 'Map only',
      mapLabel: 'Myanmar flood and landslide map',
      disclaimer: 'This information is a satellite-based estimate and does not replace official warnings. Follow the Department of Meteorology and Hydrology (DMH) and local authorities.',
      noData: 'No data yet',
      polygons: '{n} areas',
      townshipsAffected: '{n} townships affected',
      high: 'High',
      moderate: 'Moderate',
      low: 'Low',
      warnBreakdown: 'High {h} · Moderate {m}',
      sensorLine: 'Sentinel-1 radar',
      ago: '{t} ago',
      hours: '{n} h',
      minutes: '{n} min',
      days: '{n} d',
      township: 'Township',
      district: 'District',
      region: 'State / Region',
      area: 'Estimated area',
      ha: 'ha',
      hazardLevel: 'Hazard level',
      floodPopup: 'Flooded area',
      slidePopup: 'Landslide hazard',
      dEmpty: 'n/a',
      dSatellite: 'Satellite data',
      dWindow: 'Composite window',
      dBaseline: 'Dry-season baseline',
      dChecked: 'Last checked',
      dRain: 'Rainfall source',
      dRainEnd: 'Rainfall window end',
      dRainMax: 'Max 7-day rainfall',
      dRun: 'Pipeline status',
      mm: 'mm',
      bannerDemo: 'DEMO only: this is made-up sample data, not real flooding or landslides.',
      bannerNone: 'The pipeline has not produced data yet. The map fills in after the first GitHub Actions run.',
      bannerStale: 'The newest satellite data is {t} old, so the flood layer may be out of date.',
      bannerRain: 'The rainfall data is {t} old, so the landslide layer may lag behind.',
      bannerError: 'The latest pipeline run had an error. The previous data is still shown.',
      bannerLoad: 'Could not load the data. Check your connection and try again.',
      retry: 'Retry',
      locateFail: 'Could not find your location',
      status_ok: 'OK',
      status_partial: 'Partial',
      status_error: 'Error',
      status_never_run: 'Never run',
      cardRiver: 'River flood alerts (30-day forecast)',
      riverSub: '{n} river points watched',
      riverLayer: 'River flood forecast',
      suscLayer: 'Landslide-prone terrain (steep slopes)',
      legSusc: 'Steep terrain',
      legRiver0: 'River: normal',
      legRiver1: 'River: elevated',
      legRiver2: 'River: high',
      legRiver3: 'River: severe',
      riverPopup: 'River flood forecast',
      suscPopup: 'Steep terrain',
      slopeLevel: 'Steepness class',
      riverName: 'River',
      level: 'Level',
      level0: 'Normal',
      level1: 'Elevated',
      level2: 'High',
      level3: 'Severe',
      levelNone: 'No threshold available',
      nowQ: 'Discharge now',
      peakQ: 'Peak in next 30 days',
      peakOn: 'Peak date',
      thrLine: 'Flood levels (2/5/20-yr): {a} / {b} / {c}',
      riverNote: 'GloFAS river-discharge forecast only. It does not show where the water will spread, and misses small rivers and urban flooding.',
      m3s: 'm³/s',
      dRiverGen: 'River forecast generated',
      suscNote: 'Based on slope (SRTM) only, not NASA LHASA. It marks terrain where heavy rain is more likely to trigger landslides.',
      proneLayer: 'Previously flooded areas (historical data)',
      legProne: 'Previously flooded (historical)',
      pronePopup: 'Previously flooded area',
      proneClass: 'Times flooded',
      Once: 'Once',
      'Several times': 'Several times',
      Often: 'Often',
      proneNote: 'From the supplied data file: 250 m grid cells. Its source and dates are unknown. Cells that repeat in the file are read as the number of floods that reached them (not confirmed).',
      sharePct: 'Share of township',
      boundStates: 'State / region boundaries',
      boundTowns: 'Township boundaries',
      groupNow: 'Current conditions and forecasts',
      groupSat: 'Calculated from satellites',
      groupBase: 'Background information (past / fixed)',
      groupBounds: 'Boundaries',
      presetsTitle: 'Quick views',
      presetSummary: 'Overview',
      presetFlood: 'Floods',
      presetSlide: 'Landslides',
      presetClear: 'Boundaries only',
      helpBtn: 'How to read this map',
      introTitle: 'How to read this map',
      introLead: 'This map gathers information to help people prepare early. There is no need to rush: you can look at it one step at a time.',
      intro1: 'Colours show a level. Yellow = watch, orange = be careful, brick red = take extra care. No colour means nothing unusual was found yet.',
      intro2: 'Tap any place on the map to read the details and what they mean.',
      intro3: 'Forecasts are computed and are not official warnings. Always put DMH and your local authorities first.',
      intro4: 'Missing data or a failed update does not mean "no danger". If unsure, check the official source directly.',
      introOk: 'I understand',
      rainMean0: 'No unusually heavy rain is expected in the current forecast.',
      rainMean1: 'Heavy rain is possible. Keep following the weather news.',
      rainMean2: 'Very heavy rain is possible. People in low-lying places and near rivers should prepare early.',
      rainMean3: 'Exceptionally heavy rain is possible. Check DMH and local authority announcements now and follow them.',
      riverMean0: 'River flow is forecast to stay normal.',
      riverMean1: 'River flow may rise above normal. Keep watching.',
      riverMean2: 'River flow may become fairly high. People near the river should prepare early.',
      riverMean3: 'River flow may become exceptionally high. Check DMH and local authority announcements now.',
      meaningLabel: 'What it means',
      hospitalsLayer: 'Public hospitals (MIMU/CDE 2020)',
      legHospital: 'Hospital (2020 data)',
      hospPopup: 'Hospital',
      hospLevel: 'Type',
      hospBeds: 'Beds',
      hospTownship: 'Township',
      hospConf: 'Location accuracy',
      hospConfLow: 'uncertain (approximate position)',
      hospConfOk: 'rated reliable',
      hospNote: 'MIMU/CDE-Myanmar 2020 data (CC BY 4.0), not live. It does not show whether a hospital is flooded or closed now.',
      dmhLayer: 'States/regions with a DMH warning',
      legDmh: 'State/region with a DMH warning',
      dmhAlertsTitle: 'Official DMH warnings',
      dmhNone: 'No DMH warning in force was found.',
      dmhNoData: 'No DMH data yet.',
      dmhLastOk: 'Last successful fetch',
      dmhNeverOk: 'The DMH fetch has never succeeded yet.',
      dmhErrorNote: 'The last fetch had an error. Finding no warning does not mean DMH issued none. Check the DMH website directly.',
      dmhActive: 'in force',
      dmhEnded: 'ended',
      dmhValid: 'Valid',
      dmhRegions: 'Regions',
      dmhOpen: 'Original DMH page',
      dmhType_heavy_rain: 'Heavy rainfall warning',
      dmhType_cyclone: 'Cyclone warning',
      dmhType_depression: 'Depression warning',
      dmhType_strong_wind: 'Strong wind warning',
      dmhType_untimely_rain: 'Untimely rainfall warning',
      dmhType_flood: 'Flood warning',
      dmhType_tsunami: 'Tsunami warning',
      dmhType_weather_early_warning: 'Weather early warning',
      dmhType_other: 'DMH warning',
      riverDmhStation: 'DMH river gauging station',
      eventsSubTitle: 'Earthquakes and other events',
      rainLayer: 'Rain forecast (townships, 72 h)',
      legRain1: 'Rain: watch',
      legRain2: 'Rain: be careful',
      legRain3: 'Rain: take extra care',
      rainPopup: 'Rain forecast',
      rainLevel: 'Warning level',
      rl0: 'Normal',
      rl1: 'Watch',
      rl2: 'Be careful',
      rl3: 'Take extra care',
      rainPast72: 'Fell in the last 72 h',
      rainNext24: 'Next 24 h',
      rainNext72: 'Next 72 h',
      rainMax24: 'Heaviest 24 h',
      rainProne: 'Share previously flooded',
      rainWhyWet: 'Raised one level: ground already wet (150 mm or more in 72 h)',
      rainWhyProne: 'Raised one level: 15% or more of the township was flooded before',
      rainNote: 'Forecast at the township centre point only. The level is a rule of thumb (India Met Dept 24 h rain classes) and has not been checked against past floods. It is not an official warning: follow DMH announcements.',
      mm: 'mm',
      topRainTitle: 'Most rain forecast (townships, 72 h)',
      dRainGen: 'Rain forecast generated',
      publicInfoTitle: 'Weather & public information',
      publicInfoIntro: 'Seven-day city forecasts, ENSO status, and source-verified public information.',
      nextDays: 'View 7-day outlook',
      publicDisclaimer: 'Forecast-based screening only, not an official warning. Verify with original DMH/WHO/NOAA/USGS sources.',
      dmhTitle: 'Official DMH weather bulletins',
      healthTitle: 'WHO health information sources',
      healthNote: 'WHO headlines are not a verified list of local outbreaks in Myanmar. Check the original bulletin.',
      quakeTitle: 'Recent earthquakes',
      publicUnavailable: 'This data is not available yet. Open the original source.',
      sourceUpdated: 'Last data check',
      dayTemp: 'Maximum temperature',
      dayRain: 'Forecast rainfall',
      dayUV: 'UV index',
      heatRisk: 'Heat risk',
      uvRisk: 'UV exposure',
      rainRisk: 'Heavy rainfall potential',
      windRisk: 'Strong wind potential',
      risk_moderate: 'Caution',
      risk_high: 'High',
      risk_severe: 'Very high',
      ensoStatus: 'NOAA ENSO status',
      issued: 'Issued',
      earthquakeMagnitude: 'Magnitude',
      earthquakeTime: 'Time',
      noBulletins: 'No headlines could be collected in this update. Open the original source.'
    }
  };

  var MONTHS = {
    my: ['ဇန်နဝါရီ', 'ဖေဖော်ဝါရီ', 'မတ်', 'ဧပြီ', 'မေ', 'ဇွန်', 'ဇူလိုင်', 'ဩဂုတ်', 'စက်တင်ဘာ', 'အောက်တိုဘာ', 'နိုဝင်ဘာ', 'ဒီဇင်ဘာ'],
    en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  };

  var state = {
    lang: 'my',
    map: null,
    base: {},
    activeBase: null,
    layers: { flood: null, landslide: null, susceptibility: null, floodprone: null, river: null, events: null, radar: null, states: null, towns: null, rain: null, hospitals: null, dmh: null },
    official: null,
    admin1: null,
    rain: null,
    admin3: null,
    proneStats: null,
    river: null,
    publicInfo: null,
    eventData: null,
    radarTime: null,
    summary: null,
    metadata: null,
    opacity: 1,
    popupContext: null,
    lastVersion: null
  };

  // ------------------------------------------------------------------ helpers
  function $(id) { return document.getElementById(id); }

  function t(key, params) {
    var dict = I18N[state.lang] || I18N.en;
    var text = dict[key];
    if (text === undefined) { text = I18N.en[key] !== undefined ? I18N.en[key] : key; }
    if (params) {
      Object.keys(params).forEach(function (k) { text = text.replace('{' + k + '}', params[k]); });
    }
    return text;
  }

  function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function fmtNumber(value, digits) {
    if (value === null || value === undefined || isNaN(value)) { return '–'; }
    return Number(value).toLocaleString('en-US', { maximumFractionDigits: digits || 0, minimumFractionDigits: 0 });
  }

  function storageGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function storageSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* storage may be blocked */ }
  }

  // Format an ISO UTC timestamp in Myanmar Standard Time (UTC+6:30), Latin digits.
  function fmtMMT(isoString) {
    if (!isoString) { return '–'; }
    var date = new Date(isoString);
    if (isNaN(date.getTime())) { return '–'; }
    var parts = {};
    try {
      new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Asia/Yangon', day: '2-digit', month: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
      }).formatToParts(date).forEach(function (p) { parts[p.type] = p.value; });
    } catch (e) {
      var shifted = new Date(date.getTime() + 6.5 * 3600 * 1000);
      parts = {
        day: String(shifted.getUTCDate()).padStart(2, '0'), month: String(shifted.getUTCMonth() + 1),
        year: String(shifted.getUTCFullYear()), hour: String(shifted.getUTCHours()).padStart(2, '0'),
        minute: String(shifted.getUTCMinutes()).padStart(2, '0')
      };
    }
    var month = MONTHS[state.lang][parseInt(parts.month, 10) - 1] || parts.month;
    return parts.day + ' ' + month + ' ' + parts.year + ' ' + parts.hour + ':' + parts.minute + ' MMT';
  }

  function ageSpan(isoString) {
    if (!isoString) { return ''; }
    var minutes = Math.max(0, Math.round((Date.now() - new Date(isoString).getTime()) / 60000));
    if (minutes < 90) { return t('minutes', { n: Math.max(1, minutes) }); }
    if (minutes < 48 * 60) { return t('hours', { n: Math.round(minutes / 60) }); }
    return t('days', { n: Math.round(minutes / 1440) });
  }

  function ageText(isoString) {
    return isoString ? t('ago', { t: ageSpan(isoString) }) : '';
  }

  function ageHours(isoString) {
    if (!isoString) { return null; }
    return (Date.now() - new Date(isoString).getTime()) / 3600000;
  }

  // ------------------------------------------------------------------ data access
  function dataBases() {
    var bases = [];
    var host = window.location.hostname;
    var owner = CONFIG.owner;
    var repo = CONFIG.repo;
    if (!owner && /\.github\.io$/i.test(host)) {
      owner = host.split('.')[0];
      var first = window.location.pathname.split('/').filter(Boolean)[0];
      repo = repo || (first && first.indexOf('.') === -1 ? first : owner + '.github.io');
    }
    var folder = CONFIG.dataPath ? CONFIG.dataPath.replace(/^\/|\/$/g, '') + '/' : '';
    if (owner && repo) {
      bases.push('https://raw.githubusercontent.com/' + owner + '/' + repo + '/' + CONFIG.branch + '/' + folder);
    }
    // Same-origin copy (GitHub Pages, local server). Skipped when a separate data branch is used.
    if (CONFIG.dataPath) { bases.push(CONFIG.dataPath.replace(/\/$/, '') + '/'); }
    return bases;
  }

  function fetchWithTimeout(url, options, ms) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, ms || 30000);
    options = options || {};
    options.signal = controller.signal;
    return fetch(url, options).then(function (response) {
      clearTimeout(timer);
      return response;
    }, function (error) { clearTimeout(timer); throw error; });
  }

  function fetchData(fileKey, query, fresh) {
    // Offline demo build (scripts/make_demo.py) embeds sample data in window.MM_DEMO
    if (window.MM_DEMO && window.MM_DEMO[fileKey]) { return Promise.resolve(window.MM_DEMO[fileKey]); }
    // Opened as a local file: browsers block fetch(), so use the bundle in data/js/mapdata.js
    if (location.protocol === 'file:' && window.MMDATA && window.MMDATA[fileKey]) { return Promise.resolve(window.MMDATA[fileKey]); }
    var bases = dataBases();
    var name = CONFIG.files[fileKey];
    var index = 0;
    function attempt() {
      if (index >= bases.length) { return Promise.reject(new Error('Could not load ' + name)); }
      var url = bases[index++] + name + (query ? '?' + query : '');
      return fetchWithTimeout(url, fresh ? { cache: 'no-store' } : {}, fresh ? 15000 : 60000)
        .then(function (response) {
          if (!response.ok) { throw new Error('HTTP ' + response.status); }
          return response.json();
        })
        .catch(function () { return attempt(); });
    }
    return attempt();
  }

  // Tiny IndexedDB key/value cache so large GeoJSON files are downloaded only when they change.
  var idb = {
    open: function () {
      return new Promise(function (resolve, reject) {
        if (!('indexedDB' in window)) { reject(new Error('no indexedDB')); return; }
        var request = indexedDB.open('mm-hazard-cache', 1);
        request.onupgradeneeded = function () { request.result.createObjectStore('kv'); };
        request.onsuccess = function () { resolve(request.result); };
        request.onerror = function () { reject(request.error); };
      });
    },
    get: function (key) {
      return idb.open().then(function (db) {
        return new Promise(function (resolve, reject) {
          var request = db.transaction('kv', 'readonly').objectStore('kv').get(key);
          request.onsuccess = function () { resolve(request.result); };
          request.onerror = function () { reject(request.error); };
        });
      }).catch(function () { return undefined; });
    },
    set: function (key, value) {
      return idb.open().then(function (db) {
        return new Promise(function (resolve, reject) {
          var tx = db.transaction('kv', 'readwrite');
          tx.objectStore('kv').put(value, key);
          tx.oncomplete = function () { resolve(); };
          tx.onerror = function () { reject(tx.error); };
        });
      }).catch(function () { /* cache is optional */ });
    }
  };

  function loadLayerData(layerKey, metadata) {
    var layerMeta = metadata && metadata.layers && metadata.layers[layerKey];
    var version = layerMeta && layerMeta.sha256 ? layerMeta.sha256 : null;
    var cacheKey = 'geo:' + layerKey;
    var cached = version ? idb.get(cacheKey) : Promise.resolve(undefined);
    return cached.then(function (hit) {
      if (hit && hit.version === version && hit.data) { return hit.data; }
      return fetchData(layerKey, version ? 'v=' + version.slice(0, 12) : 't=' + Math.floor(Date.now() / 300000), false)
        .then(function (data) {
          if (version) { idb.set(cacheKey, { version: version, data: data }); }
          return data;
        });
    });
  }

  // ------------------------------------------------------------------ map
  function createMap() {
    var map = L.map('map', {
      preferCanvas: true,
      zoomControl: true,
      minZoom: 5,
      maxZoom: 17,
      maxBounds: CONFIG.maxBounds,
      maxBoundsViscosity: 0.8,
      tap: true,
      tapTolerance: 15,
      bounceAtZoomLimits: false,
      worldCopyJump: false
    });
    map.fitBounds(CONFIG.bounds, { padding: [8, 8] });
    L.control.scale({ imperial: false, position: 'bottomright' }).addTo(map);

    state.base.osm = L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
      maxZoom: 19, subdomains: 'abc',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, tiles <a href="https://www.hotosm.org/">HOT</a>, hosted by OSM France'
    });
    setBasemap('osm');
    state.map = map;
    return map;
  }

  function setBasemap(key) {
    if (state.activeBase && state.map) { state.map.removeLayer(state.activeBase); }
    state.activeBase = state.base[key];
    if (state.map) {
      state.activeBase.addTo(state.map);
      // keep hazard layers above the base map
      ['radar', 'floodprone', 'susceptibility', 'landslide', 'flood', 'river', 'events'].forEach(function (name) {
        var layer = state.layers[name];
        if (layer && state.map.hasLayer(layer)) { layer.bringToFront(); }
      });
    }
  }

  function floodStyle() {
    return {
      color: CONFIG.floodBorder, weight: 1.2, opacity: Math.min(1, 0.4 + state.opacity * 0.6),
      fillColor: CONFIG.floodColor, fillOpacity: CONFIG.floodFillOpacity * state.opacity
    };
  }

  function slideStyle(feature) {
    var code = feature && feature.properties ? Number(feature.properties.hazard_code) : 1;
    var color = CONFIG.slideColors[code] || CONFIG.slideColors[1];
    return {
      color: color, weight: 0.8, opacity: Math.min(1, 0.4 + state.opacity * 0.6),
      fillColor: color, fillOpacity: CONFIG.slideFillOpacity * state.opacity
    };
  }

  function suscStyle(feature) {
    var code = feature && feature.properties ? Number(feature.properties.hazard_code) : 1;
    var color = CONFIG.suscColors[code] || CONFIG.suscColors[1];
    return {
      color: color, weight: 0.6, opacity: Math.min(1, 0.3 + state.opacity * 0.5),
      fillColor: color, fillOpacity: CONFIG.suscFillOpacity * state.opacity
    };
  }

  function proneStyle(feature) {
    var code = feature && feature.properties ? Number(feature.properties.class_code) : 1;
    var color = CONFIG.proneColors[code] || CONFIG.proneColors[1];
    return {
      color: color, weight: 0.5, opacity: Math.min(1, 0.3 + state.opacity * 0.5),
      fillColor: color, fillOpacity: CONFIG.proneFillOpacity * state.opacity
    };
  }

  function buildLayer(kind, data) {
    var layer = L.geoJSON(data, {
      style: kind === 'flood' ? floodStyle : (kind === 'susceptibility' ? suscStyle : (kind === 'floodprone' ? proneStyle : slideStyle)),
      smoothFactor: 1.2
    });
    layer.on('click', function (event) {
      var feature = event.propagatedFrom && event.propagatedFrom.feature;
      if (!feature) { return; }
      state.popupContext = { kind: kind, feature: feature, latlng: event.latlng };
      openPopup();
    });
    return layer;
  }

  function popupHtml(kind, feature) {
    var p = feature.properties || {};
    var isDistrict = state.metadata && state.metadata.admin_level === 'district';
    var region = state.lang === 'my' && p.state_region_my ? p.state_region_my : p.state_region;
    var rows = '';
    var tname = state.lang === 'my' && p.township_my ? p.township_my : p.township;
    rows += '<dt>' + escapeHtml(isDistrict ? t('district') : t('township')) + '</dt><dd>' + escapeHtml(tname || '–') + '</dd>';
    if (region) { rows += '<dt>' + escapeHtml(t('region')) + '</dt><dd>' + escapeHtml(region) + '</dd>'; }
    rows += '<dt>' + escapeHtml(t('area')) + '</dt><dd>' + escapeHtml(fmtNumber(p.area_ha, 1)) + ' ' + escapeHtml(t('ha')) + '</dd>';
    var title = t(kind === 'flood' ? 'floodPopup' : (kind === 'susceptibility' ? 'suscPopup' : (kind === 'floodprone' ? 'pronePopup' : 'slidePopup')));
    if (kind === 'floodprone') {
      var cname = String(p['class'] || '');
      rows += '<dt>' + escapeHtml(t('proneClass')) + '</dt><dd><span class="chip p' + escapeHtml(String(p.class_code || 1)) + '">' + escapeHtml(t(cname) !== cname ? t(cname) : cname) + '</span></dd>';
      return '<div class="popup"><h3>' + escapeHtml(title) + '</h3><dl>' + rows + '</dl><p class="small">' + escapeHtml(t('proneNote')) + '</p></div>';
    }
    if (kind === 'susceptibility') {
      var slevel = String(p.hazard || '').toLowerCase();
      var slabel = t(slevel) !== slevel ? t(slevel) : p.hazard;
      rows += '<dt>' + escapeHtml(t('slopeLevel')) + '</dt><dd><span class="chip ' + escapeHtml(slevel) + '">' + escapeHtml(slabel) + '</span></dd>';
      return '<div class="popup"><h3>' + escapeHtml(title) + '</h3><dl>' + rows + '</dl><p class="small">' + escapeHtml(t('suscNote')) + '</p></div>';
    }
    if (kind === 'landslide') {
      var level = String(p.hazard || '').toLowerCase();
      var label = t(level) !== level ? t(level) : p.hazard;
      rows += '<dt>' + escapeHtml(t('hazardLevel')) + '</dt><dd><span class="chip ' + escapeHtml(level) + '">' + escapeHtml(label) + '</span></dd>';
    }
    return '<div class="popup"><h3>' + escapeHtml(title) + '</h3><dl>' + rows + '</dl></div>';
  }

  function openPopup() {
    var ctx = state.popupContext;
    if (!ctx || !state.map) { return; }
    L.popup({ maxWidth: 280, autoPanPadding: [16, 16] })
      .setLatLng(ctx.latlng)
      .setContent(popupHtml(ctx.kind, ctx.feature))
      .openOn(state.map);
  }

  function applyOpacity() {
    if (state.layers.flood) { state.layers.flood.setStyle(floodStyle); }
    if (state.layers.landslide) { state.layers.landslide.setStyle(slideStyle); }
    if (state.layers.susceptibility) { state.layers.susceptibility.setStyle(suscStyle); }
    if (state.layers.floodprone) { state.layers.floodprone.setStyle(proneStyle); }
    applyRainOpacity();
  }

  function syncLayerVisibility() {
    var map = state.map;
    [['states', 'toggleStates'], ['towns', 'toggleTowns'], ['rain', 'toggleRain'], ['dmh', 'toggleDmh'], ['hospitals', 'toggleHospitals'], ['floodprone', 'toggleProne'], ['susceptibility', 'toggleSusc'], ['landslide', 'toggleSlide'], ['flood', 'toggleFlood'], ['river', 'toggleRiver'], ['events', 'toggleEvents'], ['radar', 'toggleRadar']].forEach(function (pair) {
      var layer = state.layers[pair[0]];
      if (!layer) { return; }
      var wanted = $(pair[1]).checked;
      var present = map.hasLayer(layer);
      if (wanted && !present) { layer.addTo(map); }
      if (!wanted && present) { map.removeLayer(layer); }
    });
    // draw order: townships < flood-prone < susceptibility < landslide < flood < river points
    ['radar', 'towns', 'rain', 'dmh', 'floodprone', 'susceptibility', 'landslide', 'flood', 'river', 'hospitals', 'events'].forEach(function (name) {
      var layer = state.layers[name];
      if (layer && map.hasLayer(layer)) { layer.bringToFront(); }
    });
  }

  function replaceLayer(kind, data) {
    var old = state.layers[kind];
    if (old && state.map.hasLayer(old)) { state.map.removeLayer(old); }
    state.layers[kind] = buildLayer(kind, data);
    syncLayerVisibility();
  }

  // ------------------------------------------------------------------ calm start: presets, legend, intro
  var LEGEND_TOGGLES = { flood: 'toggleFlood', landslide: 'toggleSlide', floodprone: 'toggleProne', susceptibility: 'toggleSusc',
    rain: 'toggleRain', dmh: 'toggleDmh', hospitals: 'toggleHospitals', river: 'toggleRiver', events: 'toggleEvents', radar: 'toggleRadar' };

  // The legend lists only layers that are switched on and have data, so it stays short.
  function updateLegendVisibility() {
    Object.keys(LEGEND_TOGGLES).forEach(function (name) {
      var box = $(LEGEND_TOGGLES[name]);
      var show = !!(box && box.checked) && layerHasData(name);
      Array.prototype.forEach.call(document.querySelectorAll('li[data-layer="' + name + '"]'), function (li) { li.hidden = !show; });
    });
  }

  var PRESETS = {
    summary: ['toggleDmh', 'toggleRain', 'toggleRiver', 'toggleEvents', 'toggleFlood', 'toggleSlide', 'toggleStates'],
    flood: ['toggleDmh', 'toggleRain', 'toggleRiver', 'toggleFlood', 'toggleProne', 'toggleStates'],
    slide: ['toggleDmh', 'toggleRain', 'toggleSlide', 'toggleSusc', 'toggleStates'],
    clear: ['toggleStates']
  };

  function applyPreset(name) {
    var on = PRESETS[name] || [];
    Object.keys(LEGEND_TOGGLES).map(function (k) { return LEGEND_TOGGLES[k]; }).concat(['toggleStates', 'toggleTowns']).forEach(function (id) {
      var box = $(id);
      if (!box) { return; }
      var want = on.indexOf(id) >= 0;
      if (box.checked !== want) {
        box.checked = want;
        box.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    Array.prototype.forEach.call(document.querySelectorAll('.chip-btn'), function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-preset') === name ? 'true' : 'false'); });
    updateLegendVisibility();
  }

  function introSeen() {
    try { return window.localStorage.getItem('mmhm_intro_v1') === '1'; } catch (e) { return false; }
  }
  function markIntroSeen() {
    try { window.localStorage.setItem('mmhm_intro_v1', '1'); } catch (e) { /* private mode: ignore */ }
  }
  function showIntro(show) {
    var box = $('intro');
    if (!box) { return; }
    box.hidden = !show;
    if (show) { var ok = $('introOk'); if (ok) { ok.focus(); } } else { markIntroSeen(); }
  }

  function bindCalmControls() {
    Object.keys(LEGEND_TOGGLES).forEach(function (name) {
      var box = $(LEGEND_TOGGLES[name]);
      if (box) { box.addEventListener('change', updateLegendVisibility); }
    });
    Array.prototype.forEach.call(document.querySelectorAll('.chip-btn'), function (b) {
      b.addEventListener('click', function () { applyPreset(b.getAttribute('data-preset')); });
    });
    var help = $('helpBtn'); if (help) { help.addEventListener('click', function () { showIntro(true); }); }
    var ok = $('introOk'); if (ok) { ok.addEventListener('click', function () { showIntro(false); }); }
    var backdrop = $('intro');
    if (backdrop) {
      backdrop.addEventListener('click', function (event) { if (event.target === backdrop) { showIntro(false); } });
      document.addEventListener('keydown', function (event) { if (event.key === 'Escape' && !backdrop.hidden) { showIntro(false); } });
    }
    if (!introSeen()) { showIntro(true); }
  }

  // ------------------------------------------------------------------ hospitals (from the weather website's MIMU/CDE dataset)
  function hospitalPopupHtml(p) {
    var my = state.lang === 'my';
    var name = my && p.n ? p.n : (p.ne || p.n);
    var level = my && p.l ? p.l : (p.le || p.l);
    var township = my && p.t ? p.t : (p.te || p.t);
    var region = my && p.r ? p.r : (p.re || p.r);
    var low = /inaccurate|township-level|bestGuess/i.test(p.c || '');
    var rows = '';
    if (level) { rows += '<dt>' + escapeHtml(t('hospLevel')) + '</dt><dd>' + escapeHtml(level) + '</dd>'; }
    if (p.b) { rows += '<dt>' + escapeHtml(t('hospBeds')) + '</dt><dd>' + escapeHtml(p.b) + '</dd>'; }
    rows += '<dt>' + escapeHtml(t('hospTownship')) + '</dt><dd>' + escapeHtml(township || '–') + '</dd>';
    rows += '<dt>' + escapeHtml(t('region')) + '</dt><dd>' + escapeHtml(region || '–') + '</dd>';
    rows += '<dt>' + escapeHtml(t('hospConf')) + '</dt><dd>' + escapeHtml(t(low ? 'hospConfLow' : 'hospConfOk')) + '</dd>';
    return '<div class="popup"><h3>' + escapeHtml(name || t('hospPopup')) + '</h3><dl>' + rows + '</dl><p class="small">' + escapeHtml(t('hospNote')) + '</p></div>';
  }

  function buildHospitalLayer(data) {
    var old = state.layers.hospitals;
    if (old && state.map.hasLayer(old)) { state.map.removeLayer(old); }
    state.layers.hospitals = null;
    if (!data || !data.features || !data.features.length) { return; }
    state.layers.hospitals = L.geoJSON(data, {
      pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, { radius: 4.5, color: '#ffffff', weight: 1.2, fillColor: '#1b7f5c', fillOpacity: 0.95 });
      },
      onEachFeature: function (feature, layer) {
        layer.bindPopup(function () { return hospitalPopupHtml(feature.properties || {}); }, { maxWidth: 300, autoPanPadding: [16, 16] });
      }
    });
  }

  // ------------------------------------------------------------------ official DMH warnings (from the weather website)
  function normRegion(value) { return String(value || '').toLowerCase().replace(/[^a-z]/g, ''); }

  function activeOfficialAlerts() {
    var now = Date.now();
    return ((state.official && state.official.alerts) || []).filter(function (a) {
      var from = Date.parse(a.valid_from), to = Date.parse(a.valid_to);
      return Number.isFinite(from) && Number.isFinite(to) && from <= now && now <= to;
    });
  }

  function alertTitle(a) {
    var title = a.title || {};
    return (state.lang === 'my' ? title.my || title.en : title.en || title.my) || t('dmhType_' + a.type);
  }

  function regionHasAlert(adminName, alerts) {
    var name = normRegion(adminName);
    return alerts.filter(function (a) {
      return (a.regions || []).some(function (r) {
        var rn = normRegion(r);
        return rn === 'myanmar' || (rn && name.indexOf(rn) === 0);
      });
    });
  }

  function rebuildDmhLayer() {
    var old = state.layers.dmh;
    if (old && state.map.hasLayer(old)) { state.map.removeLayer(old); }
    state.layers.dmh = null;
    var alerts = activeOfficialAlerts();
    if (state.admin1 && alerts.length) {
      var features = (state.admin1.features || []).filter(function (f) { return regionHasAlert((f.properties || {}).n, alerts).length; });
      if (features.length) {
        state.layers.dmh = L.geoJSON({ type: 'FeatureCollection', features: features }, {
          style: { color: '#c2410c', weight: 3, dashArray: '8 5', fillColor: '#fb923c', fillOpacity: 0.16 },
          onEachFeature: function (feature, layer) {
            layer.bindPopup(function () {
              var p = feature.properties || {};
              var list = regionHasAlert(p.n, alerts).map(function (a) {
                return '<li>' + escapeHtml(t('dmhType_' + a.type)) + ': ' + escapeHtml(alertTitle(a)) + '</li>';
              }).join('');
              return '<div class="popup"><h3>' + escapeHtml(state.lang === 'my' && p.nm ? p.nm : p.n) + '</h3><ul class="alert-list">' + list + '</ul></div>';
            }, { maxWidth: 300, autoPanPadding: [16, 16] });
          }
        });
      }
    }
    updateEmptyLayers();
    syncLayerVisibility();
  }

  function renderDmhAlerts() {
    var container = $('dmhAlerts');
    var status = $('dmhStatus');
    if (!container) { return; }
    container.textContent = '';
    var data = state.official;
    var alerts = ((data && data.alerts) || []).slice().sort(function (a, b) { return Date.parse(b.valid_from) - Date.parse(a.valid_from); });
    var active = activeOfficialAlerts();
    var count = $('alertCount');
    if (count) {
      var events = state.eventData && Array.isArray(state.eventData.events) ? state.eventData.events.length : 0;
      count.textContent = String(events + active.length);
      var fab = $('alertsToggle');
      if (fab) { fab.classList.toggle('no-events', events + active.length === 0); }
    }
    if (status) {
      var s = (data && data.status) || {};
      status.textContent = !data ? t('dmhNoData')
        : (s.last_success_at ? t('dmhLastOk') + ': ' + fmtMMT(s.last_success_at) : t('dmhNeverOk'));
      if (data && s.last_error) {
        var warn = document.createElement('span');
        warn.className = 'public-note';
        warn.textContent = ' ' + t('dmhErrorNote');
        status.appendChild(document.createElement('br'));
        status.appendChild(warn);
      }
    }
    if (!alerts.length) {
      var none = document.createElement('p'); none.className = 'public-meta'; none.textContent = data ? t('dmhNone') : t('dmhNoData');
      container.appendChild(none);
      return;
    }
    alerts.slice(0, 12).forEach(function (a) {
      var isActive = active.indexOf(a) >= 0;
      var card = document.createElement('article'); card.className = 'public-row event-row' + (isActive ? '' : ' ended');
      var heading = document.createElement('h4');
      heading.textContent = t('dmhType_' + a.type) + ' · ' + (isActive ? t('dmhActive') : t('dmhEnded'));
      var title = document.createElement('p'); title.className = 'public-meta'; title.textContent = alertTitle(a);
      var meta = document.createElement('p'); meta.className = 'public-meta';
      meta.textContent = t('dmhValid') + ': ' + fmtMMT(a.valid_from) + ' – ' + fmtMMT(a.valid_to) + (a.regions && a.regions.length ? ' · ' + t('dmhRegions') + ': ' + a.regions.join(', ') : '');
      card.appendChild(heading); card.appendChild(title); card.appendChild(meta);
      var link = (a.links && (state.lang === 'my' ? a.links.my || a.links.en : a.links.en || a.links.my)) || a.url;
      if (link && /^https:\/\//i.test(link)) { appendSafeLink(card, t('dmhOpen'), link); }
      container.appendChild(card);
    });
  }

  function loadOfficialAlerts() {
    return fetchData('officialAlerts', 't=' + Math.floor(Date.now() / 60000), true)
      .then(function (data) { state.official = data; return data; })
      .catch(function () { return null; });
  }

  // ------------------------------------------------------------------ township rain forecast
  function rainIndex() {
    var index = {};
    ((state.rain && state.rain.townships) || []).forEach(function (row) { index[row.k] = row; });
    return index;
  }

  function rainKey(feature) {
    var p = feature.properties || {};
    return p.n + '|' + p.s;
  }

  function rainStyleFor(row) {
    var level = row ? row.lv : 0;
    if (!level) { return { stroke: false, fill: true, fillColor: '#ffffff', fillOpacity: 0 }; }
    var color = CONFIG.rainColors[level] || CONFIG.rainColors[1];
    return { color: color, weight: 1, opacity: 0.9, fillColor: color, fillOpacity: 0.42 * Math.max(0.35, state.opacity) };
  }

  function rainPopupHtml(row) {
    var chip = '<span class="chip r' + row.lv + '">' + escapeHtml(t('rl' + row.lv)) + '</span>';
    var name = state.lang === 'my' && row.nm ? row.nm : row.n;
    var region = state.lang === 'my' && row.sm ? row.sm : row.s;
    var rows = '';
    rows += '<dt>' + escapeHtml(t('region')) + '</dt><dd>' + escapeHtml(region) + '</dd>';
    rows += '<dt>' + escapeHtml(t('rainLevel')) + '</dt><dd>' + chip + '</dd>';
    rows += '<dt>' + escapeHtml(t('rainPast72')) + '</dt><dd>' + escapeHtml(fmtNumber(row.past72, 0)) + ' ' + escapeHtml(t('mm')) + '</dd>';
    rows += '<dt>' + escapeHtml(t('rainNext24')) + '</dt><dd>' + escapeHtml(fmtNumber(row.next24, 0)) + ' ' + escapeHtml(t('mm')) + '</dd>';
    rows += '<dt>' + escapeHtml(t('rainNext72')) + '</dt><dd>' + escapeHtml(fmtNumber(row.next72, 0)) + ' ' + escapeHtml(t('mm')) + '</dd>';
    rows += '<dt>' + escapeHtml(t('rainMax24')) + '</dt><dd>' + escapeHtml(fmtNumber(row.max24, 0)) + ' ' + escapeHtml(t('mm')) + '</dd>';
    rows += '<dt>' + escapeHtml(t('rainProne')) + '</dt><dd>' + escapeHtml(fmtNumber(row.prone, 0)) + '%</dd>';
    var why = (row.why || []).map(function (code) {
      return '<p class="small">' + escapeHtml(t(code === 'wet' ? 'rainWhyWet' : 'rainWhyProne')) + '</p>';
    }).join('');
    var meaning = '<p class="meaning"><strong>' + escapeHtml(t('meaningLabel')) + ':</strong> ' + escapeHtml(t('rainMean' + row.lv)) + '</p>';
    return '<div class="popup"><h3>' + escapeHtml(name) + '</h3>' + meaning + '<dl>' + rows + '</dl>' + why +
      '<p class="small">' + escapeHtml(t('rainNote')) + '</p></div>';
  }

  function rebuildRain() {
    var old = state.layers.rain;
    if (old && state.map.hasLayer(old)) { state.map.removeLayer(old); }
    state.layers.rain = null;
    if (!state.admin3 || !state.rain || !state.rain.townships || !state.rain.townships.length) { updateEmptyLayers(); return; }
    var index = rainIndex();
    state.layers.rain = L.geoJSON(state.admin3, {
      filter: function (feature) { return !!index[rainKey(feature)]; },
      style: function (feature) { return rainStyleFor(index[rainKey(feature)]); },
      onEachFeature: function (feature, layer) {
        var row = index[rainKey(feature)];
        layer.bindPopup(function () { return rainPopupHtml(row); }, { maxWidth: 300, maxHeight: 340, autoPanPadding: [16, 16] });
      }
    });
    updateEmptyLayers();
    syncLayerVisibility();
  }

  function applyRainOpacity() {
    var layer = state.layers.rain;
    if (!layer) { return; }
    var index = rainIndex();
    layer.setStyle(function (feature) { return rainStyleFor(index[rainKey(feature)]); });
  }

  function loadRain() {
    return fetchData('rain', 't=' + Math.floor(Date.now() / 60000), true)
      .then(function (data) { state.rain = data; return data; })
      .catch(function () { return null; });
  }

  // ------------------------------------------------------------------ boundaries + empty layers
  function townLabel(p) {
    return state.lang === 'my' && p.nm ? p.nm : p.n;
  }

  function buildBoundaryLayers(admin1, admin3) {
    var map = state.map;
    if (!map.getPane('boundary')) {
      map.createPane('boundary');
      map.getPane('boundary').style.zIndex = 430;
      map.getPane('boundary').style.pointerEvents = 'none';
    }
    if (admin1 && !state.layers.states) {
      state.layers.states = L.geoJSON(admin1, { pane: 'boundary', interactive: false,
        style: { color: '#12263a', weight: 1.5, fill: false, opacity: 0.85 } });
    }
    if (admin3 && !state.layers.towns) {
      state.layers.towns = L.geoJSON(admin3, {
        style: { color: '#6b7785', weight: 0.8, fill: true, fillOpacity: 0, opacity: 0.9 },
        onEachFeature: function (feature, layer) {
          layer.bindTooltip(function () {
            var p = feature.properties || {};
            return escapeHtml(townLabel(p)) + (p.d ? ' · ' + escapeHtml(state.lang === 'my' && p.dm ? p.dm : p.d) : '');
          }, { sticky: true });
        }
      });
    }
  }

  function layerHasData(name) {
    if (name === 'rain') { return !!(state.rain && state.rain.townships && state.rain.townships.length && state.layers.rain); }
    if (name === 'river') { return !!(state.river && state.river.points && state.river.points.length); }
    if (name === 'events') { return !!(state.eventData && state.eventData.events && state.eventData.events.some(function (e) { return e.lat !== null && e.lon !== null && e.lat !== undefined && e.lon !== undefined && Number.isFinite(Number(e.lat)) && Number.isFinite(Number(e.lon)); })); }
    if (name === 'radar') { return !!state.layers.radar; }
    if (name === 'dmh') { return !!state.layers.dmh; }
    if (name === 'hospitals') { return !!state.layers.hospitals; }
    var layer = state.layers[name];
    return !!(layer && layer.getLayers && layer.getLayers().length);
  }

  // Layers that have no data yet (for example before the first pipeline run) are hidden from the panel.
  function updateEmptyLayers() {
    var toggles = { flood: 'toggleFlood', landslide: 'toggleSlide', susceptibility: 'toggleSusc', river: 'toggleRiver', floodprone: 'toggleProne', events: 'toggleEvents', radar: 'toggleRadar', rain: 'toggleRain', dmh: 'toggleDmh', hospitals: 'toggleHospitals' };
    Object.keys(toggles).forEach(function (name) {
      var has = layerHasData(name);
      var label = $(toggles[name]).closest('label');
      if (label) { label.hidden = !has; }
      Array.prototype.forEach.call(document.querySelectorAll('li[data-layer="' + name + '"]'), function (li) { li.hidden = !has; });
    });
    updateLegendVisibility();
    // the summary cards only make sense once the pipeline has produced something
    var metrics = document.querySelector('.metrics');
    if (metrics) {
      metrics.hidden = !(layerHasData('flood') || layerHasData('landslide') || layerHasData('river') || layerHasData('susceptibility'));
      if (state.map) { state.map.invalidateSize(); }
    }
  }

  // ------------------------------------------------------------------ Myanmar-only view
  // Everything outside the country outline is covered, so only Myanmar is visible.
  function addCountryMask(outline) {
    var map = state.map;
    var geometry = outline && outline.features && outline.features[0] && outline.features[0].geometry;
    if (!geometry) { return; }
    if (!map.getPane('mask')) {
      map.createPane('mask');
      map.getPane('mask').style.zIndex = 410;          // above tiles and hazard polygons, below markers/popups
      map.getPane('mask').style.pointerEvents = 'none';
      map.createPane('border');
      map.getPane('border').style.zIndex = 420;
      map.getPane('border').style.pointerEvents = 'none';
    }
    var polygons = geometry.type === 'MultiPolygon' ? geometry.coordinates : [geometry.coordinates];
    var world = [[-89, -179.9], [-89, 179.9], [89, 179.9], [89, -179.9]];
    var holes = [];
    polygons.forEach(function (poly) {
      poly.forEach(function (ring, index) {
        if (index === 0) {
          holes.push(ring.map(function (c) { return [c[1], c[0]]; }));
        }
      });
    });
    L.polygon([world].concat(holes), {
      pane: 'mask', stroke: false, fillColor: '#e8edf2', fillOpacity: 1, interactive: false
    }).addTo(map);
    var lines = [];
    polygons.forEach(function (poly) { poly.forEach(function (ring) { lines.push(ring.map(function (c) { return [c[1], c[0]]; })); }); });
    L.polyline(lines, { pane: 'border', color: '#12263a', weight: 1.4, opacity: 0.8, interactive: false, smoothFactor: 1 }).addTo(map);
  }

  // ------------------------------------------------------------------ river forecast
  function fmtDay(iso) {
    if (!iso) { return '–'; }
    var parts = String(iso).slice(0, 10).split('-');
    var month = MONTHS[state.lang][parseInt(parts[1], 10) - 1] || parts[1];
    return parseInt(parts[2], 10) + ' ' + month + ' ' + parts[0];
  }

  function riverColor(level) {
    return level === null || level === undefined ? CONFIG.riverUnknown : (CONFIG.riverColors[level] || CONFIG.riverUnknown);
  }

  function sparkline(point) {
    var q = (point.series && point.series.q) || [];
    var nums = q.filter(function (v) { return v !== null && v !== undefined; });
    if (nums.length < 2) { return ''; }
    var thr = point.thresholds || null;
    var w = 240, h = 70, pad = 4;
    var hi = Math.max.apply(null, nums), lo = Math.min.apply(null, nums);
    if (thr) { hi = Math.max(hi, thr.t2); }
    if (hi === lo) { hi = lo + 1; }
    var span = hi - lo;
    function x(i) { return pad + (w - 2 * pad) * i / (q.length - 1); }
    function y(v) { return h - pad - (h - 2 * pad) * (v - lo) / span; }
    var pts = [];
    q.forEach(function (v, i) { if (v !== null && v !== undefined) { pts.push(x(i).toFixed(1) + ',' + y(v).toFixed(1)); } });
    var lines = '';
    if (thr) {
      [['t2', '#b8940a'], ['t5', '#d9640a'], ['t20', '#d00000']].forEach(function (pair) {
        var v = thr[pair[0]];
        if (v >= lo && v <= hi) {
          lines += '<line x1="' + pad + '" x2="' + (w - pad) + '" y1="' + y(v).toFixed(1) + '" y2="' + y(v).toFixed(1) +
            '" stroke="' + pair[1] + '" stroke-width="1" stroke-dasharray="4 3"/>';
        }
      });
    }
    var todayIdx = q.length > 0 && point.series.start ? Math.round((Date.parse(new Date().toISOString().slice(0, 10)) - Date.parse(point.series.start)) / 86400000) : -1;
    var today = todayIdx >= 0 && todayIdx < q.length
      ? '<line x1="' + x(todayIdx).toFixed(1) + '" x2="' + x(todayIdx).toFixed(1) + '" y1="0" y2="' + h + '" stroke="#12263a" stroke-opacity=".35" stroke-width="1"/>'
      : '';
    return '<svg class="spark" viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="' + escapeHtml(t('peakQ')) + '">' +
      lines + today + '<polyline fill="none" stroke="#0077be" stroke-width="2" points="' + pts.join(' ') + '"/></svg>';
  }

  function riverPopupHtml(point) {
    var level = point.level;
    var chipClass = level === null || level === undefined ? 'rn' : 'r' + level;
    var chipText = level === null || level === undefined ? t('levelNone') : t('level' + level);
    var rows = '';
    rows += '<dt>' + escapeHtml(t('riverName')) + '</dt><dd>' + escapeHtml(point.river) + '</dd>';
    rows += '<dt>' + escapeHtml(t('level')) + '</dt><dd><span class="chip ' + chipClass + '">' + escapeHtml(chipText) + '</span></dd>';
    rows += '<dt>' + escapeHtml(t('nowQ')) + '</dt><dd>' + escapeHtml(fmtNumber(point.now_q, 0)) + ' ' + escapeHtml(t('m3s')) + '</dd>';
    rows += '<dt>' + escapeHtml(t('peakQ')) + '</dt><dd>' + escapeHtml(fmtNumber(point.peak_q, 0)) + ' ' + escapeHtml(t('m3s')) + '</dd>';
    rows += '<dt>' + escapeHtml(t('peakOn')) + '</dt><dd>' + escapeHtml(fmtDay(point.peak_date)) + '</dd>';
    var thr = point.thresholds;
    var thrLine = thr ? '<p class="small">' + escapeHtml(t('thrLine', { a: fmtNumber(thr.t2, 0), b: fmtNumber(thr.t5, 0), c: fmtNumber(thr.t20, 0) })) + '</p>' : '';
    var stationName = state.lang === 'my' && point.name_my ? point.name_my : point.name;
    var stationTag = point.station_id ? '<p class="small">' + escapeHtml(t('riverDmhStation')) + '</p>' : '';
    var riverMeaning = (level === null || level === undefined) ? '' : '<p class="meaning"><strong>' + escapeHtml(t('meaningLabel')) + ':</strong> ' + escapeHtml(t('riverMean' + level)) + '</p>';
    return '<div class="popup"><h3>' + escapeHtml(stationName) + '</h3>' + stationTag + riverMeaning + '<dl>' + rows + '</dl>' + sparkline(point) + thrLine +
      '<p class="small">' + escapeHtml(t('riverNote')) + '</p></div>';
  }

  function buildRiverLayer(data) {
    var group = L.featureGroup();
    ((data && data.points) || []).forEach(function (point) {
      if (typeof point.lat !== 'number' || typeof point.lon !== 'number') { return; }
      var marker = L.circleMarker([point.lat, point.lon], {
        radius: point.level >= 2 ? 9 : 7, color: '#ffffff', weight: 2,
        fillColor: riverColor(point.level), fillOpacity: 0.95
      });
      marker.on('click', function (event) {
        L.popup({ maxWidth: 280, maxHeight: 340, autoPanPadding: [16, 16] })
          .setLatLng(event.latlng || marker.getLatLng())
          .setContent(riverPopupHtml(point))
          .openOn(state.map);
      });
      marker.addTo(group);
    });
    return group;
  }

  function replaceRiver(data) {
    var old = state.layers.river;
    if (old && state.map.hasLayer(old)) { state.map.removeLayer(old); }
    state.river = data;
    state.layers.river = buildRiverLayer(data);
    syncLayerVisibility();
  }

  function loadRiver() {
    return fetchData('river', 't=' + Math.floor(Date.now() / 60000), true)
      .then(function (data) { replaceRiver(data); return data; })
      .catch(function () { return null; });
  }

  // ------------------------------------------------------------------ source-attributed observed events (USGS / GDACS / optional NASA FIRMS)
  function eventKindLabel(kind, event) {
    if (kind === 'earthquake') return t('eventEarthquake');
    if (kind === 'fire_detection') return t('eventFire');
    if (kind === 'weather_risk') {
      var type = event && event.hazard_type;
      var labels = state.lang === 'my'
        ? { heavy_rain: 'မိုးသည်းထန်နိုင်ခြေ', strong_wind: 'လေပြင်းအန္တရာယ်', extreme_heat: 'အပူလွန်ကဲနိုင်ခြေ', uv: 'UV အညွှန်းမြင့်မားနိုင်ခြေ' }
        : { heavy_rain: 'Heavy rainfall screening', strong_wind: 'Strong wind screening', extreme_heat: 'Extreme heat screening', uv: 'High UV screening' };
      return labels[type] || (state.lang === 'my' ? 'ရာသီဥတုအန္တရာယ် ခန့်မှန်းစစ်ဆေးမှု' : 'Weather hazard screening');
    }
    return t('eventAlert');
  }

  function eventColor(kind, event) {
    if (kind === 'earthquake') return '#b91c1c';
    if (kind === 'fire_detection') return '#ea580c';
    if (kind === 'weather_risk') {
      var level = event && event.risk_level;
      return level === 'severe' ? '#b91c1c' : level === 'high' ? '#ea580c' : '#ca8a04';
    }
    return '#7c3aed';
  }

  function eventPopupHtml(event) {
    var rows = '<dt>' + escapeHtml(t('eventStatus')) + '</dt><dd>' + escapeHtml(eventKindLabel(event.kind, event)) + '</dd>';
    if (event.status === 'forecast' && event.forecast_date) rows += '<dt>' + escapeHtml(state.lang === 'my' ? 'ခန့်မှန်းရက်' : 'Forecast date') + '</dt><dd>' + escapeHtml(event.forecast_date) + '</dd>';
    if (event.risk_level) rows += '<dt>' + escapeHtml(state.lang === 'my' ? 'စစ်ဆေးမှုအဆင့်' : 'Screening level') + '</dt><dd>' + escapeHtml(event.risk_level) + '</dd>';
    if (event.magnitude !== null && event.magnitude !== undefined && event.magnitude !== '') rows += '<dt>' + escapeHtml(t('eventMagnitude')) + '</dt><dd>' + escapeHtml(event.magnitude) + '</dd>';
    if (event.depth_km !== null && event.depth_km !== undefined) rows += '<dt>' + escapeHtml(t('eventDepth')) + '</dt><dd>' + escapeHtml(fmtNumber(event.depth_km, 1)) + ' km</dd>';
    if (event.time_utc) rows += '<dt>' + escapeHtml(t('earthquakeTime')) + '</dt><dd>' + escapeHtml(fmtMMT(event.time_utc)) + '</dd>';
    rows += '<dt>' + escapeHtml(t('eventSource')) + '</dt><dd>' + escapeHtml(event.source || '–') + '</dd>';
    var link = event.url && /^https:\/\//i.test(event.url) ? '<p class="small"><a href="' + escapeHtml(event.url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(state.lang === 'my' ? 'မူရင်းဒေတာကို ကြည့်ရန်' : 'Open source record') + '</a></p>' : '';
    return '<div class="popup"><h3>' + escapeHtml(event.title || eventKindLabel(event.kind)) + '</h3><dl>' + rows + '</dl>' + link + '<p class="small">' + escapeHtml(event.details || '') + '</p></div>';
  }

  function replaceEvents(data) {
    var old = state.layers.events;
    if (old && state.map && state.map.hasLayer(old)) state.map.removeLayer(old);
    state.eventData = data || { events: [] };
    var features = (state.eventData.events || []).filter(function (e) { return e.lat !== null && e.lon !== null && e.lat !== undefined && e.lon !== undefined && Number.isFinite(Number(e.lat)) && Number.isFinite(Number(e.lon)); }).map(function (e) {
      return { type: 'Feature', properties: e, geometry: { type: 'Point', coordinates: [Number(e.lon), Number(e.lat)] } };
    });
    state.layers.events = L.geoJSON({ type: 'FeatureCollection', features: features }, {
      pointToLayer: function (feature, latlng) {
        var e = feature.properties || {};
        return L.circleMarker(latlng, { radius: e.kind === 'earthquake' ? 7 : 8, color: '#fff', weight: 2, fillColor: eventColor(e.kind, e), fillOpacity: .95 });
      },
      onEachFeature: function (feature, layer) {
        layer.on('click', function (ev) { L.popup({ maxWidth: 300, maxHeight: 360, autoPanPadding: [16, 16] }).setLatLng(ev.latlng).setContent(eventPopupHtml(feature.properties || {})).openOn(state.map); });
      }
    });
    renderLiveEvents();
    syncLayerVisibility();
  }

  function renderLiveEvents() {
    var container = $('eventAlerts');
    var updated = $('eventsUpdated');
    var data = state.eventData;
    if (!container) return;
    container.textContent = '';
    var events = data && Array.isArray(data.events) ? data.events.slice() : [];
    if (updated) {
      updated.textContent = t('eventsUpdated') + ': ' + (data && data.generated_utc ? fmtMMT(data.generated_utc) : t('dEmpty'));
      var checks = data && data.source_checks ? Object.keys(data.source_checks).filter(function (key) { return data.source_checks[key] && data.source_checks[key].status === 'error'; }) : [];
      if (checks.length) updated.textContent += state.lang === 'my' ? ' · ရင်းမြစ် ' + checks.length + ' ခု အပ်ဒိတ်မအောင်မြင်ပါ' : ' · ' + checks.length + ' source update(s) failed';
    }
    var count = $('alertCount');
    if (count) count.textContent = String(events.length + activeOfficialAlerts().length);
    var alertsButton = $('alertsToggle');
    if (alertsButton) alertsButton.classList.toggle('no-events', events.length + activeOfficialAlerts().length === 0);
    if (!events.length) {
      var empty = document.createElement('p'); empty.className = 'public-meta'; empty.textContent = t('eventsEmpty'); container.appendChild(empty);
      var sourceUrls = [['DMH Myanmar','https://www.moezala.gov.mm/en'],['GDACS','https://www.gdacs.org/'],['USGS Earthquakes','https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php']];
      sourceUrls.forEach(function (entry) { appendSafeLink(container, entry[0], entry[1]); });
      return;
    }
    events.slice(0, 35).forEach(function (e) {
      var card = document.createElement('article'); card.className = 'public-row event-row';
      var heading = document.createElement('h4'); heading.textContent = eventKindLabel(e.kind, e) + ' · ' + (e.kind === 'weather_risk' && state.lang === 'my' && e.city_my ? e.city_my : (e.title || ''));
      var meta = document.createElement('p'); meta.className = 'public-meta';
      var bits = []; if (e.time_utc) bits.push(e.status === 'forecast' && e.forecast_date ? ((state.lang === 'my' ? 'ခန့်မှန်းရက် ' : 'Forecast ') + e.forecast_date) : fmtMMT(e.time_utc)); if (e.magnitude !== null && e.magnitude !== undefined && e.magnitude !== '') bits.push(t('eventMagnitude') + ' ' + e.magnitude); if (e.risk_level) bits.push((state.lang === 'my' ? 'အဆင့် ' : 'Level ') + e.risk_level); if (e.source) bits.push(e.source);
      meta.textContent = bits.join(' · ');
      card.appendChild(heading); card.appendChild(meta);
      if (e.details) { var detail = document.createElement('p'); detail.className = 'public-meta'; detail.textContent = e.details; card.appendChild(detail); }
      if (e.url && /^https:\/\//i.test(e.url)) appendSafeLink(card, state.lang === 'my' ? 'မူရင်းရင်းမြစ်' : 'Source record', e.url);
      if (e.lat !== null && e.lon !== null && e.lat !== undefined && e.lon !== undefined && Number.isFinite(Number(e.lat)) && Number.isFinite(Number(e.lon))) {
        var mapBtn = document.createElement('button'); mapBtn.type = 'button'; mapBtn.className = 'event-map-btn'; mapBtn.textContent = state.lang === 'my' ? 'မြေပုံပေါ်ကြည့်ရန်' : 'Show on map';
        mapBtn.addEventListener('click', function () { if (state.map) { state.map.setView([Number(e.lat), Number(e.lon)], Math.max(state.map.getZoom(), 7)); if (state.layers.events) state.layers.events.eachLayer(function (layer) { var ll = layer.getLatLng && layer.getLatLng(); if (ll && Math.abs(ll.lat-Number(e.lat))<.001 && Math.abs(ll.lng-Number(e.lon))<.001) layer.fire('click', {latlng:ll}); }); } });
        card.appendChild(mapBtn);
      }
      container.appendChild(card);
    });
    if (data && data.disclaimer) { var note = document.createElement('p'); note.className = 'public-note'; note.textContent = data.disclaimer; container.appendChild(note); }
  }

  // ------------------------------------------------------------------ RainViewer past radar overlay (imagery only, not a forecast)
  function loadRadar() {
    var endpoint = 'https://api.rainviewer.com/public/weather-maps.json';
    return fetchWithTimeout(endpoint, { cache: 'no-store' }, 12000).then(function (response) {
      if (!response.ok) throw new Error('Radar metadata HTTP ' + response.status);
      return response.json();
    }).then(function (payload) {
      var frames = payload && payload.radar && payload.radar.past;
      if (!payload.host || !Array.isArray(frames) || !frames.length) throw new Error('No past radar frames');
      var frame = frames[frames.length - 1];
      var url = payload.host + frame.path + '/256/{z}/{x}/{y}/2/1_0.png';
      var next = L.tileLayer(url, { opacity: .64, maxZoom: 17, maxNativeZoom: 7, tileSize: 256,
        attribution: '<a href="https://www.rainviewer.com/" target="_blank" rel="noopener noreferrer">Weather data by RainViewer</a>' });
      var old = state.layers.radar;
      if (old && state.map.hasLayer(old)) state.map.removeLayer(old);
      state.layers.radar = next;
      state.radarTime = frame.time ? new Date(frame.time * 1000).toISOString() : null;
      var label = $('radarStatus');
      if (label) label.textContent = t('radarStatus') + ': ' + (state.radarTime ? fmtMMT(state.radarTime) : t('dEmpty')) + ' · RainViewer';
      syncLayerVisibility();
      updateEmptyLayers();
      return next;
    }).catch(function (error) {
      if (window.console && console.warn) console.warn('Rain radar unavailable:', error);
      var label = $('radarStatus'); if (label) label.textContent = t('radarUnavailable') + ' · RainViewer';
      updateEmptyLayers();
      return null;
    });
  }

  // ------------------------------------------------------------------ dashboard
  function renderRanking(listId, items, valueKey, unitKey) {
    var list = $(listId);
    list.innerHTML = '';
    if (!items || !items.length) {
      var li = document.createElement('li');
      li.className = 'empty';
      li.textContent = t('dEmpty');
      list.appendChild(li);
      return;
    }
    items.slice(0, 5).forEach(function (item) {
      var li = document.createElement('li');
      var name = document.createElement('span');
      name.className = 'name';
      var region = state.lang === 'my' && item.state_region_my ? item.state_region_my : item.state_region;
      var tn = state.lang === 'my' && item.township_my ? item.township_my : item.township;
      name.textContent = tn + (region ? ' (' + region + ')' : '');
      var val = document.createElement('span');
      val.className = 'val';
      val.textContent = fmtNumber(item[valueKey || 'area_ha'], 0) + ' ' + t(unitKey || 'ha');
      li.appendChild(name);
      li.appendChild(val);
      list.appendChild(li);
    });
  }

  function addInfoRow(list, label, value) {
    var dt = document.createElement('dt');
    dt.textContent = label;
    var dd = document.createElement('dd');
    dd.textContent = value;
    list.appendChild(dt);
    list.appendChild(dd);
  }

  function renderDashboard() {
    var s = state.summary || {};
    var flood = s.flood || {};
    var slide = s.landslide || {};
    var sat = s.satellite || {};
    var rain = s.rainfall || {};
    var meta = state.metadata || {};

    var hasFlood = flood.total_area_ha !== null && flood.total_area_ha !== undefined;
    $('mFloodValue').textContent = hasFlood ? fmtNumber(flood.total_area_ha, 0) : '–';
    $('mFloodSub').textContent = hasFlood
      ? t('polygons', { n: fmtNumber(flood.polygon_count) }) + ' · ' + t('townshipsAffected', { n: fmtNumber(flood.townships_affected) })
      : t('noData');

    var hasSlide = slide.updated_utc !== null && slide.updated_utc !== undefined;
    $('mSlideValue').textContent = hasSlide ? fmtNumber(slide.townships_warned) : '–';
    $('mSlideSub').textContent = hasSlide
      ? t('warnBreakdown', { h: fmtNumber(slide.townships_high), m: fmtNumber(slide.townships_moderate) })
      : t('noData');

    $('mTimeValue').textContent = sat.latest_scene_utc ? fmtMMT(sat.latest_scene_utc) : '–';
    $('mTimeSub').textContent = sat.latest_scene_utc ? t('sensorLine') + ' · ' + ageText(sat.latest_scene_utc) : t('noData');

    var riverPoints = (state.river && state.river.points) || [];
    var riverAlerts = riverPoints.filter(function (pt) { return pt.level >= 2 || pt.level_max >= 3; }).length;
    $('mRiverValue').textContent = riverPoints.length ? fmtNumber(riverAlerts) : '–';
    $('mRiverSub').textContent = riverPoints.length ? t('riverSub', { n: fmtNumber(riverPoints.length) }) : t('noData');

    renderRanking('topFlood', flood.top_townships, 'area_ha');
    renderRanking('topProne', state.proneStats && state.proneStats.top_townships, 'area_ha');
    var rainRows = ((state.rain && state.rain.townships) || []).slice().sort(function (a, b) { return b.next72 - a.next72; }).slice(0, 5).map(function (r) {
      return { township: r.n, township_my: r.nm, state_region: r.s, state_region_my: r.sm, next72: r.next72 };
    });
    renderRanking('topRain', rainRows, 'next72', 'mm');
    renderRanking('topSlide', slide.top_townships, 'area_ha');

    var info = $('dataInfoList');
    info.innerHTML = '';
    var na = t('dEmpty');
    addInfoRow(info, t('dSatellite'), sat.latest_scene_utc ? fmtMMT(sat.latest_scene_utc) : na);
    addInfoRow(info, t('dWindow'), sat.window_start_utc ? fmtMMT(sat.window_start_utc) + ' → ' + fmtMMT(sat.window_end_utc) : na);
    addInfoRow(info, t('dBaseline'), sat.baseline_period || na);
    addInfoRow(info, t('dRain'), rain.source || na);
    addInfoRow(info, t('dRainEnd'), rain.window_end_utc ? fmtMMT(rain.window_end_utc) : na);
    addInfoRow(info, t('dRainMax'), rain.max_7d_mm !== null && rain.max_7d_mm !== undefined ? fmtNumber(rain.max_7d_mm, 0) + ' ' + t('mm') : na);
    addInfoRow(info, t('dChecked'), meta.last_run_utc ? fmtMMT(meta.last_run_utc) : na);
    addInfoRow(info, t('dRun'), t('status_' + (meta.run_status || 'never_run')));
    addInfoRow(info, t('dRainGen'), state.rain && state.rain.generated_utc ? fmtMMT(state.rain.generated_utc) : na);
    addInfoRow(info, t('dRiverGen'), state.river && state.river.generated_utc ? fmtMMT(state.river.generated_utc) : na);

    renderBanner();
  }

  // ------------------------------------------------------------------ public sources, forecast-based screening, and recent events
  function publicRiskLabel(risk) {
    var typeKey = { heat: 'heatRisk', uv: 'uvRisk', heavy_rain: 'rainRisk', wind: 'windRisk' }[risk.type] || risk.type;
    var advice = {
      heat: state.lang === 'my' ? 'ရေကို မကြာခဏသောက်ပြီး နေပြင်းချိန်တွင် အလုပ်ကြမ်းကို လျှော့ပါ။' : 'Drink water regularly and reduce strenuous activity during the hottest hours.',
      uv: state.lang === 'my' ? 'အရိပ်တွင်နေပါ၊ ဦးထုပ်နှင့် အကာအကွယ်အဝတ်အစား အသုံးပြုပါ။' : 'Seek shade and use a hat and protective clothing outdoors.',
      heavy_rain: state.lang === 'my' ? 'DMH သတိပေးချက်ကို စစ်ဆေးပါ။ ရေစီးနေသော လမ်း/ချောင်းကို မဖြတ်ပါနှင့်။' : 'Check DMH bulletins and do not walk or drive through moving floodwater.',
      wind: state.lang === 'my' ? 'အပြင်ရှိ လွတ်လပ်သောပစ္စည်းများကို လုံခြုံစေပြီး DMH သတိပေးချက်ကို စစ်ဆေးပါ။' : 'Secure loose outdoor objects and check official DMH warnings.'
    };
    return t(typeKey) + ': ' + t('risk_' + (risk.level || 'moderate')) + (advice[risk.type] ? ' — ' + advice[risk.type] : '');
  }

  function appendSafeLink(container, title, url, extra) {
    var row = document.createElement('div');
    row.className = 'public-row';
    var link = document.createElement('a');
    link.textContent = title || url;
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    row.appendChild(link);
    if (extra) {
      var note = document.createElement('p');
      note.className = 'public-meta';
      note.textContent = extra;
      row.appendChild(note);
    }
    container.appendChild(row);
  }

  function renderLinkItems(containerId, section, fallbackUrl) {
    var container = $(containerId);
    if (!container) return;
    container.textContent = '';
    var items = section && Array.isArray(section.items) ? section.items : [];
    if (section && section.updated_utc) {
      var updatedNote = document.createElement('p');
      updatedNote.className = 'public-meta';
      updatedNote.textContent = (state.lang === 'my' ? 'နောက်ဆုံးရယူချိန်: ' : 'Last retrieved: ') + fmtMMT(section.updated_utc);
      container.appendChild(updatedNote);
    }
    var displayed = 0;
    if (items.length) {
      items.slice(0, 6).forEach(function (item) {
        if (item && item.url && /^https:\/\//i.test(item.url)) {
          appendSafeLink(container, item.title || item.place || item.url, item.url,
            item.time_utc ? t('earthquakeTime') + ': ' + fmtMMT(item.time_utc) + (item.magnitude !== undefined ? ' · ' + t('earthquakeMagnitude') + ' ' + item.magnitude : '') : '');
          displayed += 1;
        }
      });
    }
    if (!displayed && fallbackUrl) {
      var message = document.createElement('p');
      message.className = 'public-meta';
      message.textContent = t('publicUnavailable') + ' ' + (section && section.status === 'ok' ? t('noBulletins') : '');
      container.appendChild(message);
      appendSafeLink(container, section && section.source ? section.source : fallbackUrl, fallbackUrl);
    }
  }

  function renderPublicInfo() {
    var data = state.publicInfo;
    var updated = $('publicInfoUpdated');
    var weatherContainer = $('weatherCards');
    var ensoContainer = $('ensoCard');
    if (!weatherContainer || !ensoContainer) return;
    weatherContainer.textContent = '';
    ensoContainer.textContent = '';
    if (!data) {
      if (updated) updated.textContent = t('publicUnavailable');
      weatherContainer.textContent = t('publicUnavailable');
      appendSafeLink(weatherContainer, 'Open-Meteo Forecast API', 'https://open-meteo.com/en/docs');
      ensoContainer.textContent = '';
      appendSafeLink(ensoContainer, 'NOAA CPC ENSO Diagnostic Discussion', 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml');
      renderLinkItems('dmhItems', null, 'https://www.moezala.gov.mm/index.php/en');
      renderLinkItems('healthItems', null, 'https://www.who.int/southeastasia/outbreaks-and-emergencies');
      renderLinkItems('quakeItems', null, 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson');
      return;
    }
    if (updated) {
      var failedCount = Object.keys(data.source_checks || {}).filter(function (key) { return data.source_checks[key] && data.source_checks[key].status === 'error'; }).length;
      updated.textContent = t('sourceUpdated') + ': ' + (data.generated_utc ? fmtMMT(data.generated_utc) : t('dEmpty'));
      if (failedCount) updated.textContent += state.lang === 'my' ? ' · ရင်းမြစ် ' + failedCount + ' ခု ရယူမရ၍ ဒေတာဟောင်း ဖြစ်နိုင်သည်။' : ' · ' + failedCount + ' source(s) failed; cached information may be old.';
    }

    var weather = data.weather || {};
    if (weather.updated_utc) {
      var weatherTime = document.createElement('p');
      weatherTime.className = 'public-meta';
      weatherTime.textContent = (state.lang === 'my' ? 'ခန့်မှန်းချက် ထုတ်ချိန်: ' : 'Forecast updated: ') + fmtMMT(weather.updated_utc);
      weatherContainer.appendChild(weatherTime);
    }
    var cities = Array.isArray(weather.cities) ? weather.cities : [];
    if (cities.length) {
      var count = 0;
      cities.slice().sort(function (a, b) {
        function score(city) { var f = city.forecast && city.forecast[0]; return f && f.risks ? f.risks.reduce(function (sum, risk) { return sum + (risk.level === 'severe' ? 3 : risk.level === 'high' ? 2 : 1); }, 0) : 0; }
        return score(b) - score(a);
      }).slice(0, 8).forEach(function (city) {
        var today = city.forecast && city.forecast[0];
        if (!today) return;
        count += 1;
        var card = document.createElement('article');
        card.className = 'public-weather-card';
        var heading = document.createElement('h4');
        heading.textContent = state.lang === 'my' ? (city.name_my || city.name) : city.name;
        card.appendChild(heading);
        var metrics = document.createElement('p');
        metrics.className = 'public-weather-metrics';
        var temp = today.temp_max_c;
        var rain = today.precipitation_mm;
        var uv = today.uv_index_max;
        metrics.textContent = (temp !== null && temp !== undefined ? t('dayTemp') + ': ' + Math.round(temp) + '°C' : '') +
          (rain !== null && rain !== undefined ? ' · ' + t('dayRain') + ': ' + Number(rain).toFixed(1) + ' mm' : '') +
          (uv !== null && uv !== undefined ? ' · ' + t('dayUV') + ': ' + Number(uv).toFixed(1) : '');
        card.appendChild(metrics);
        if (Array.isArray(today.risks) && today.risks.length) {
          var riskList = document.createElement('ul');
          riskList.className = 'public-risk-list';
          today.risks.forEach(function (risk) {
            var li = document.createElement('li');
            li.className = 'risk-' + (risk.level || 'moderate');
            li.textContent = publicRiskLabel(risk);
            riskList.appendChild(li);
          });
          card.appendChild(riskList);
        } else {
          var okay = document.createElement('p');
          okay.className = 'public-meta';
          okay.textContent = state.lang === 'my' ? 'သတ်မှတ်ထားသော အပူ/UV/မိုး/လေ threshold ကို မကျော်ပါ။' : 'No configured heat/UV/rain/wind screening threshold exceeded.';
          card.appendChild(okay);
        }
        if (Array.isArray(city.forecast) && city.forecast.length > 1) {
          var outlook = document.createElement('details');
          outlook.className = 'forecast-more';
          var summaryLine = document.createElement('summary');
          summaryLine.textContent = t('nextDays');
          outlook.appendChild(summaryLine);
          var days = document.createElement('ul');
          days.className = 'forecast-days';
          city.forecast.slice(1, 7).forEach(function (day) {
            var dayLine = document.createElement('li');
            var pieces = [day.date];
            if (day.temp_max_c !== null && day.temp_max_c !== undefined) pieces.push(Math.round(day.temp_max_c) + '°C');
            if (day.precipitation_mm !== null && day.precipitation_mm !== undefined) pieces.push(Number(day.precipitation_mm).toFixed(1) + ' mm');
            if (day.uv_index_max !== null && day.uv_index_max !== undefined) pieces.push('UV ' + Number(day.uv_index_max).toFixed(1));
            dayLine.textContent = pieces.join(' · ');
            days.appendChild(dayLine);
          });
          outlook.appendChild(days);
          card.appendChild(outlook);
        }
        weatherContainer.appendChild(card);
      });
      if (!count) weatherContainer.textContent = t('publicUnavailable');
    } else {
      weatherContainer.textContent = t('publicUnavailable');
      appendSafeLink(weatherContainer, 'Open-Meteo Forecast API', (data.sources && data.sources.weather && data.sources.weather.url) || 'https://open-meteo.com/en/docs');
    }

    var enso = data.enso || {};
    var ensoTitle = document.createElement('h4');
    ensoTitle.textContent = t('ensoStatus') + ': ' + (enso.alert_status || (enso.status === 'ok' ? 'See source bulletin' : t('dEmpty')));
    ensoContainer.appendChild(ensoTitle);
    if (enso.issued_date) {
      var dateLine = document.createElement('p');
      dateLine.className = 'public-meta';
      dateLine.textContent = t('issued') + ': ' + enso.issued_date;
      ensoContainer.appendChild(dateLine);
    }
    if (enso.synopsis) {
      var synopsis = document.createElement('p');
      synopsis.textContent = enso.synopsis;
      ensoContainer.appendChild(synopsis);
    }
    appendSafeLink(ensoContainer, (data.sources && data.sources.enso && data.sources.enso.name) || 'NOAA CPC ENSO discussion', enso.url || 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml');

    renderLinkItems('dmhItems', data.dmh, 'https://www.moezala.gov.mm/index.php/en');
    renderLinkItems('healthItems', data.health, 'https://www.who.int/southeastasia/outbreaks-and-emergencies');
    renderLinkItems('quakeItems', data.earthquakes, 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson');
  }

  function loadPublicInfo() {
    return fetchData('publicInfo', 't=' + Math.floor(Date.now() / 60000), true)
      .then(function (data) { state.publicInfo = data; renderPublicInfo(); return data; })
      .catch(function (error) { if (window.console) console.warn('Public information unavailable:', error); renderPublicInfo(); return null; });
  }

  function renderBanner() {
    var banner = $('banner');
    var meta = state.metadata;
    var s = state.summary || {};
    var message = '';
    var kind = '';
    if (window.MM_DEMO) {
      message = t('bannerDemo'); kind = 'info';
    } else if (state.loadFailed) {
      message = t('bannerLoad'); kind = 'error';
    } else if (!meta || !meta.last_run_utc || (s.flood && s.flood.total_area_ha === null && !(s.satellite && s.satellite.latest_scene_utc))) {
      message = t('bannerNone'); kind = 'info';
    } else if (meta.run_status === 'error') {
      message = t('bannerError'); kind = 'error';
    } else {
      var satAge = ageHours(s.satellite && s.satellite.latest_scene_utc);
      var rainStale = s.rainfall && s.rainfall.stale;
      if (satAge !== null && satAge > CONFIG.staleSatelliteHours) {
        message = t('bannerStale', { t: ageSpan(s.satellite.latest_scene_utc) });
      } else if (rainStale) {
        var days = s.rainfall.data_age_days;
        message = t('bannerRain', { t: t('days', { n: days !== null && days !== undefined ? Math.round(days) : '?' }) });
      }
    }
    banner.className = 'banner' + (kind ? ' ' + kind : '');
    banner.hidden = !message;
    banner.textContent = message;
    if (state.loadFailed) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn secondary';
      button.textContent = t('retry');
      button.addEventListener('click', function () { init(true); });
      banner.appendChild(button);
    }
    updateBannerSpace();
  }

  // Keep the legend above the status banner so the two never overlap (important on phones).
  function updateBannerSpace() {
    var banner = $('banner');
    var wrap = banner && banner.parentNode;
    if (!wrap) { return; }
    var space = banner.hidden ? 0 : banner.offsetHeight + 10;
    wrap.style.setProperty('--banner-space', space + 'px');
  }

  // ------------------------------------------------------------------ i18n application
  function applyLang(lang) {
    state.lang = lang;
    storageSet('mm-lang', lang);
    document.documentElement.lang = lang === 'my' ? 'my' : 'en';
    document.title = t('title');
    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n]'), function (el) {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n-aria]'), function (el) {
      el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria')));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n-title]'), function (el) {
      el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
    });
    Array.prototype.forEach.call(document.querySelectorAll('.lang-btn'), function (btn) {
      btn.setAttribute('aria-pressed', btn.getAttribute('data-lang') === lang ? 'true' : 'false');
    });
    renderDashboard();
    renderPublicInfo();
    renderLiveEvents();
    renderDmhAlerts();
    var radarStatusEl = $('radarStatus');
    if (radarStatusEl) radarStatusEl.textContent = state.radarTime ? t('radarStatus') + ': ' + fmtMMT(state.radarTime) + ' · RainViewer' : t('radarUnavailable') + ' · RainViewer';
    if (state.map && state.map._popup && state.map._popup.isOpen() && state.popupContext) { openPopup(); }
  }

  // ------------------------------------------------------------------ UI wiring
  function wireUi() {
    Array.prototype.forEach.call(document.querySelectorAll('.lang-btn'), function (btn) {
      btn.addEventListener('click', function () { applyLang(btn.getAttribute('data-lang')); });
    });

    var panel = $('layersPanel');
    var toggle = $('layersToggle');
    function setPanel(open) {
      panel.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.hidden = open;  // the panel has its own close button; avoid two controls on top of each other
    }
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && panel.classList.contains('open')) { setPanel(false); toggle.focus(); }
    });
    toggle.addEventListener('click', function () { setPanel(!panel.classList.contains('open')); });
    $('panelClose').addEventListener('click', function () { setPanel(false); });
    if (!window.matchMedia('(max-width: 720px)').matches) {
      setPanel(true);
    } else {
      // On phones the legend now has many entries; start it collapsed so it does not cover the map.
      var legend = $('legend');
      if (legend) { legend.open = false; }
    }

    $('toggleFlood').addEventListener('change', syncLayerVisibility);
    $('toggleSlide').addEventListener('change', syncLayerVisibility);
    $('toggleSusc').addEventListener('change', syncLayerVisibility);
    $('toggleProne').addEventListener('change', syncLayerVisibility);
    $('toggleStates').addEventListener('change', syncLayerVisibility);
    $('toggleRain').addEventListener('change', syncLayerVisibility);
    $('toggleDmh').addEventListener('change', syncLayerVisibility);
    bindCalmControls();
    $('toggleHospitals').addEventListener('change', syncLayerVisibility);
    $('toggleTowns').addEventListener('change', syncLayerVisibility);
    $('toggleRiver').addEventListener('change', syncLayerVisibility);
    $('toggleEvents').addEventListener('change', syncLayerVisibility);
    $('toggleRadar').addEventListener('change', syncLayerVisibility);
    var alertsButton = $('alertsToggle');
    if (alertsButton) alertsButton.addEventListener('click', function () {
      panel.classList.add('open'); toggle.setAttribute('aria-expanded', 'true'); toggle.hidden = true;
      var details = $('liveAlerts'); if (details) { details.open = true; details.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
    });

    var pending = null;
    $('opacity').addEventListener('input', function (event) {
      var value = Number(event.target.value);
      $('opacityOut').textContent = value + '%';
      state.opacity = value / 100;
      if (pending) { cancelAnimationFrame(pending); }
      pending = requestAnimationFrame(function () { applyOpacity(); pending = null; });
    });

    $('locateBtn').addEventListener('click', function () {
      state.map.locate({ setView: true, maxZoom: 12, enableHighAccuracy: true, timeout: 15000 });
    });
    state.map.on('locationfound', function (event) {
      if (state.locationMarker) { state.map.removeLayer(state.locationMarker); }
      state.locationMarker = L.circleMarker(event.latlng, {
        radius: 8, color: '#fff', weight: 3, fillColor: '#1d6fe0', fillOpacity: 1
      }).addTo(state.map);
    });
    state.map.on('locationerror', function () { window.alert(t('locateFail')); });

    $('focusBtn').addEventListener('click', function () {
      var app = $('app');
      var on = !app.classList.contains('focus');
      app.classList.toggle('focus', on);
      $('focusBtn').setAttribute('aria-pressed', on ? 'true' : 'false');
      setTimeout(function () { state.map.invalidateSize(); }, 50);
    });

    window.addEventListener('resize', function () { state.map.invalidateSize(); updateBannerSpace(); });
  }

  // ------------------------------------------------------------------ loading
  function init(isRetry) {
    var loader = $('loader');
    loader.classList.remove('done');
    state.loadFailed = false;
    return fetchData('metadata', 't=' + Math.floor(Date.now() / 60000), true)
      .then(function (metadata) {
        state.metadata = metadata;
        return fetchData('summary', 't=' + Math.floor(Date.now() / 60000), true);
      })
      .then(function (summary) {
        state.summary = summary;
        state.lastVersion = (state.metadata.layers.flood.sha256 || '') + '|' + (state.metadata.layers.landslide.sha256 || '') + '|' + (summary.generated_utc || '');
        renderDashboard();
        return Promise.all([
          loadLayerData('flood', state.metadata).catch(function () { return null; }),
          loadLayerData('landslide', state.metadata).catch(function () { return null; }),
          loadLayerData('susceptibility', state.metadata).catch(function () { return null; }),
          loadRiver(),
          fetchData('floodprone').catch(function () { return null; }),
          fetchData('proneStats').catch(function () { return null; }),
          fetchData('outline').catch(function () { return null; }),
          fetchData('admin1').catch(function () { return null; }),
          fetchData('admin3').catch(function () { return null; }),
          fetchData('events').catch(function () { return null; }),
          loadRain(),
          fetchData('hospitals').catch(function () { return null; }),
          loadOfficialAlerts()
        ]);
      })
      .then(function (results) {
        if (results[0]) { replaceLayer('flood', results[0]); }
        if (results[1]) { replaceLayer('landslide', results[1]); }
        if (results[2]) { replaceLayer('susceptibility', results[2]); }
        if (results[4]) { replaceLayer('floodprone', results[4]); }
        if (results[5]) { state.proneStats = results[5]; }
        if (results[6] && !state.maskAdded) { addCountryMask(results[6]); state.maskAdded = true; }
        buildBoundaryLayers(results[7], results[8]);
        state.admin3 = results[8];
        state.admin1 = results[7];
        rebuildRain();
        buildHospitalLayer(results[11]);
        rebuildDmhLayer();
        renderDmhAlerts();
        // Before the pipeline has produced anything, show the historical flood-prone areas so the map is not empty.
        if (!['dmh', 'rain', 'river', 'flood', 'landslide'].some(layerHasData)) {
          var baseline = $('toggleProne');
          if (baseline && !baseline.checked) { baseline.checked = true; baseline.dispatchEvent(new Event('change', { bubbles: true })); }
        }
        if (results[9]) { replaceEvents(results[9]); } else { renderLiveEvents(); }
        updateEmptyLayers();
        syncLayerVisibility();
        renderDashboard();
        if (!results[0] && !results[1]) { throw new Error('layers unavailable'); }
      })
      .catch(function (error) {
        if (window.console) { console.warn('Data load failed:', error); }
        state.loadFailed = !state.metadata;
        renderDashboard();
      })
      .then(function () { loader.classList.add('done'); });
  }

  function scheduleRefresh() {
    setInterval(function () {
      if (document.hidden) { return; }
      fetchData('metadata', 't=' + Date.now(), true).then(function (metadata) {
        var version = (metadata.layers.flood.sha256 || '') + '|' + (metadata.layers.landslide.sha256 || '');
        var current = (state.lastVersion || '').split('|').slice(0, 2).join('|');
        if (version !== current || metadata.last_run_utc !== (state.metadata && state.metadata.last_run_utc)) {
          init(true);
        }
      }).catch(function () { /* keep showing what we have */ });
      loadRiver().then(function () { updateEmptyLayers(); renderDashboard(); });
      loadRain().then(function () { rebuildRain(); renderDashboard(); });
      loadOfficialAlerts().then(function () { rebuildDmhLayer(); renderDmhAlerts(); });
      loadPublicInfo();
      fetchData('events', 't=' + Math.floor(Date.now() / 60000), true).then(function (data) { replaceEvents(data); updateEmptyLayers(); }).catch(function () { /* retain prior event feed */ });
      loadRadar();
    }, CONFIG.refreshMinutes * 60 * 1000);
  }

  // ------------------------------------------------------------------ start
  function start() {
    var saved = storageGet('mm-lang');
    state.lang = saved === 'en' || saved === 'my' ? saved : 'my';

    // Leaflet is loaded from a third-party CDN. If the network or an old
    // service worker blocks it, show a readable error instead of crashing.
    if (!window.L || typeof window.L.map !== 'function') {
      var mapEl = document.getElementById('map');
      if (mapEl) {
        mapEl.innerHTML = '<div class="map-error" role="alert">' +
          '<strong>မြေပုံကို မဖွင့်နိုင်ပါ။ / Map could not load.</strong><br>' +
          'အင်တာနက်ချိတ်ဆက်မှုကို စစ်ဆေးပြီး စာမျက်နှာကို ပြန်ဖွင့်ပါ။ ' +
          'If this persists, unregister the old Service Worker for localhost and reload.' +
          '</div>';
      }
      var loading = document.querySelector('.loading');
      if (loading) loading.hidden = true;
      // Keep public information available even when a map CDN is blocked.
      // A map-library failure should not hide forecasts and official source links.
      applyLang(state.lang);
      loadPublicInfo();
      fetchData('events', 't=' + Math.floor(Date.now() / 60000), true).then(function (data) { state.eventData = data; renderLiveEvents(); }).catch(function () { renderLiveEvents(); });
      return;
    }

    createMap();
    wireUi();
    loadRadar();
    applyLang(state.lang);
    loadPublicInfo();
    init(false).then(scheduleRefresh);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
