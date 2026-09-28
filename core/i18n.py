"""Small, explicit navigation dictionary for the beginner interface."""

NAVIGATION = {
    "Overview": "ওভারভিউ",
    "Projects & Data": "প্রকল্প ও ডেটা",
    "Listed Company Data": "তালিকাভুক্ত কোম্পানির ডেটা",
    "Portfolio Management": "পোর্টফোলিও ব্যবস্থাপনা",
    "Data Quality Center": "ডেটার মান যাচাই",
    "Data Readiness": "ডেটা প্রস্তুতি",
    "Financial Statements": "আর্থিক বিবরণী",
    "Ratio Analysis": "অনুপাত বিশ্লেষণ",
    "DuPont Analysis": "ডুপন্ট বিশ্লেষণ",
    "Trend Analysis": "প্রবণতা বিশ্লেষণ",
    "Working Capital": "কার্যকরী মূলধন",
    "Cash Flow": "নগদ প্রবাহ",
    "Peer Comparison": "সমকক্ষ তুলনা",
    "Key Insights & Risk Flags": "মূল অন্তর্দৃষ্টি ও ঝুঁকি",
    "Scenario Lab": "দৃশ্যপট পরীক্ষা",
    "Health Score Methodology": "স্বাস্থ্য স্কোর পদ্ধতি",
    "Generated Report": "প্রস্তুত প্রতিবেদন",
    "CredGrid AI": "ক্রেডগ্রিড এআই",
    "Valuation Lab": "মূল্যায়ন ল্যাব",
    "Industry Comparison": "একই শিল্পের তুলনা",
    "Local Governance": "স্থানীয় পরিচালনা",
    "About Falcon Finalysis": "ফ্যালকন ফাইনালাইসিস পরিচিতি",
}


def nav_label(english: str, language: str) -> str:
    if language == "বাংলা":
        return f"{NAVIGATION.get(english, english)} · {english}"
    return english


def workflow_guide(language: str) -> str:
    if language == "বাংলা":
        return ("**শুরু করুন:** ডেটা নির্বাচন করুন → উৎস ও মান যাচাই করুন → বিশ্লেষণ দেখুন → "
                "দৃশ্যপট পরীক্ষা করুন → মানব পর্যালোচনার পর সিদ্ধান্ত নিন।")
    return ("**Start here:** choose data → verify sources and quality → review analysis → "
            "test scenarios → make a human-reviewed decision.")
