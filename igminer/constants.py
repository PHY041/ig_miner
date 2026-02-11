"""Default hashtag lists and constants."""

IG_APP_ID = "936619743392459"
IG_BASE_URL = "https://www.instagram.com"

# Base64-like alphabet for shortcode ↔ media PK conversion
SHORTCODE_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)

# Default hashtags for daemon mode (China travel — swap with your own)
DEFAULT_HASHTAGS = [
    "beijing", "shanghai", "chengdu", "xian", "guilin", "chongqing",
    "hangzhou", "guangzhou", "shenzhen", "suzhou", "nanjing", "kunming",
    "lijiang", "zhangjiajie", "harbin", "qingdao", "xiamen", "dalian",
    "wuhan", "sanya", "luoyang", "dali", "yangshuo", "huangshan",
    "lhasa", "pingyao", "fenghuang", "dunhuang",
    "travelchina", "chinatravel", "visitchina", "chinatrip",
    "explorechina", "discoverchina", "beautifulchina", "amazingchina",
    "chinesefood", "chineseculture", "chinesearchitecture",
    "greatwallofchina", "forbiddencity", "terracottawarriors",
]
