
# config.py

# Video settings
MAX_VIDEO_MB = 20
MAX_VIDEO_SECONDS = 300
MAX_OUTPUT_MB = 49

# Processing settings
PROCESSING_TIMEOUT_SECONDS = 2700

# Queue settings
MAX_CONCURRENT_PROCESSING = 1

# Telegram bot settings
WELCOME_TEXT = (
    "ভিডিও পাঠান—আমি ব্যাকগ্রাউন্ড মিউজিক কমিয়ে "
    "কথা/কণ্ঠ যতটা সম্ভব রেখে ভিডিও ফেরত দেব।"
)

HELP_TEXT = (
    "ভিডিও বা ভিডিও ফাইল পাঠান।\n"
    f"সর্বোচ্চ সাইজ: {MAX_VIDEO_MB} MB\n"
    f"সর্বোচ্চ দৈর্ঘ্য: {MAX_VIDEO_SECONDS} সেকেন্ড।"
)
