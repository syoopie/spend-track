"""Curated default categorization word bank - seeded once as immutable rules.

Coverage comes from two tiers: (1) real merchant strings pulled from the
user's own historical UOB transactions, and (2) common Singapore
merchant/keyword knowledge for categories the real data didn't cover
(Beauty, Sports & Hobbies, Home, Healthcare, Education). This bank never
targets "Others" or "PayNow Transfers" - those are pure fallback outcomes
produced by the categorization engine itself (engine/rules.py), not rule
matches.
"""

DEFAULT_RULE_BANK: dict[str, list[tuple[str, str]]] = {
    "Food & Drink": [
        # From the user's real transaction history
        ("FOUR LEAVES", "Four Leaves"),
        ("FINEST PAYA LEBAR QUARTER", "The Finest"),
        ("SUPERGREEN", "Supergreen"),
        ("KAJIKEN", "Kajiken"),
        ("FORTUNA-TERRAZZA", "Fortuna Terrazza"),
        ("SMP*OTTIE PANCAKES", "Ottie Pancakes"),
        ("SMP*DEBIA*ALCHEMIST", "Debia Alchemist"),
        ("KS FOOD BEVERAGES", "KS Food & Beverages"),
        ("CHOC A BLOC", "Choc A Bloc"),
        ("DOMINOS PIZZA", "Domino's Pizza"),
        ("CHAGEE", "Chagee"),
        ("MAIXIANG", "Maixiang"),
        ("IJOOZ", "iJooz"),
        ("BIRDS OF PARADISE", "Birds of Paradise"),
        # General SG knowledge
        ("STARBUCKS", "Starbucks"),
        ("MCDONALD", "McDonald's"),
        ("KFC", "KFC"),
        ("BURGER KING", "Burger King"),
        ("SUBWAY", "Subway"),
        ("PIZZA HUT", "Pizza Hut"),
        ("TOAST BOX", "Toast Box"),
        ("YA KUN", "Ya Kun Kaya Toast"),
        ("KOI THE", "KOI Thé"),
        ("LIHO", "LiHO"),
        ("GONG CHA", "Gong Cha"),
        ("HEYTEA", "HeyTea"),
        ("MOS BURGER", "MOS Burger"),
        ("DIN TAI FUNG", "Din Tai Fung"),
        ("SWENSEN", "Swensen's"),
        ("ASTONS", "Astons"),
        ("PUTIEN", "PUTIEN"),
        ("CRYSTAL JADE", "Crystal Jade"),
        ("PARADISE DYNASTY", "Paradise Dynasty"),
        ("OLD CHANG KEE", "Old Chang Kee"),
        ("GRABFOOD", "GrabFood"),
        ("FOODPANDA", "foodpanda"),
        ("DELIVEROO", "Deliveroo"),
        ("BREADTALK", "BreadTalk"),
        ("POLAR PUFFS", "Polar Puffs & Cakes"),
        ("TIONG BAHRU BAKERY", "Tiong Bahru Bakery"),
        ("KOPITIAM", "Kopitiam"),
        ("HAWKER", "Hawker Centre"),
    ],
    "Transport": [
        # From the user's real transaction history
        ("BUS/MRT", "Public Transport"),
        ("PARKING.SG", "Parking.sg"),
        # General SG knowledge - specific ride-hailing services before bare "GRAB"
        ("GRABPAY", "GrabPay"),
        ("GRABCAR", "GrabCar"),
        ("GRABHIRE", "GrabHire"),
        ("GOJEK", "Gojek"),
        ("COMFORTDELGRO", "ComfortDelGro"),
        ("CDG ZIG", "CDG Zig"),
        ("SMRT", "SMRT"),
        ("SBS TRANSIT", "SBS Transit"),
        ("TRANSITLINK", "TransitLink"),
        ("EZ-LINK", "EZ-Link"),
        ("SHELL", "Shell"),
        ("CALTEX", "Caltex"),
        ("ESSO", "Esso"),
        ("SPC", "SPC"),
        ("TADA", "TADA"),
        ("RYDE", "Ryde"),
        ("GRAB", "Grab"),
    ],
    "Groceries": [
        # From the user's real transaction history
        ("SHENG SIONG", "Sheng Siong"),
        ("COLD STORAGE", "Cold Storage"),
        # General SG knowledge
        ("NTUC FAIRPRICE", "NTUC FairPrice"),
        ("FAIRPRICE", "FairPrice"),
        ("GIANT", "Giant"),
        ("PRIME SUPERMARKET", "Prime Supermarket"),
        ("MUSTAFA", "Mustafa Centre"),
        ("DON DON DONKI", "Don Don Donki"),
        ("REDMART", "RedMart"),
        ("JASONS", "Jasons"),
    ],
    "Shopping": [
        # From the user's real transaction history
        ("SHOPEE", "Shopee"),
        # General SG knowledge
        ("LAZADA", "Lazada"),
        ("TAOBAO", "Taobao"),
        ("UNIQLO", "Uniqlo"),
        ("ZARA", "Zara"),
        ("MUJI", "Muji"),
        ("CHALLENGER", "Challenger"),
        ("TAKASHIMAYA", "Takashimaya"),
        ("ROBINSONS", "Robinsons"),
        ("METRO", "METRO"),
        ("BEST DENKI", "Best Denki"),
        ("AMAZON", "Amazon"),
    ],
    "Bills & Fees": [
        # From the user's real transaction history
        ("APPLE.COM/BILL", "Apple"),
        ("GOMO BY SINGTEL", "Gomo by Singtel"),
        # General SG knowledge
        ("SINGTEL", "Singtel"),
        ("STARHUB", "StarHub"),
        ("CIRCLES.LIFE", "Circles.Life"),
        ("SP SERVICES", "SP Services"),
        ("SP GROUP", "SP Group"),
        ("CITY GAS", "City Gas"),
        ("TOWN COUNCIL", "Town Council"),
        ("CONSERVANCY", "Conservancy Charges"),
        ("ANNUAL FEE", "Annual Fee"),
        ("LATE PAYMENT FEE", "Late Payment Fee"),
        ("CASH ADVANCE FEE", "Cash Advance Fee"),
        ("PRUDENTIAL", "Prudential"),
        ("GREAT EASTERN", "Great Eastern"),
        ("NTUC INCOME", "NTUC Income"),
        ("MSIG", "MSIG"),
        ("AIA", "AIA"),
        ("M1 ", "M1"),
    ],
    "Entertainment": [
        # From the user's real transaction history
        ("NETFLIX", "Netflix"),
        ("GARDENS BY THE BAY", "Gardens by the Bay"),
        # General SG knowledge
        ("SPOTIFY", "Spotify"),
        ("DISNEY+", "Disney+"),
        ("YOUTUBE PREMIUM", "YouTube Premium"),
        ("APPLE MUSIC", "Apple Music"),
        ("AMAZON PRIME VIDEO", "Amazon Prime Video"),
        ("GOLDEN VILLAGE", "Golden Village"),
        ("CATHAY CINEMA", "Cathay Cineplexes"),
        ("SHAW THEATRE", "Shaw Theatres"),
        ("STEAM", "Steam"),
        ("PLAYSTATION", "PlayStation"),
        ("NINTENDO", "Nintendo"),
        ("UNIVERSAL STUDIOS", "Universal Studios Singapore"),
        ("SEA AQUARIUM", "S.E.A. Aquarium"),
        ("SENTOSA", "Sentosa"),
        ("TIMEZONE", "Timezone"),
        ("ZOUK", "Zouk"),
        ("MARINA BAY SANDS", "Marina Bay Sands"),
    ],
    "Beauty": [
        ("SEPHORA", "Sephora"),
        ("WATSONS", "Watsons"),
        ("GUARDIAN", "Guardian"),
        ("LUXASIA", "Luxasia"),
        ("THE BODY SHOP", "The Body Shop"),
        ("KIEHL'S", "Kiehl's"),
        ("INNISFREE", "Innisfree"),
        ("SASA", "Sa Sa"),
        ("NAIL", "Nail Salon"),
        ("BARBER", "Barber"),
        ("HAIR STUDIO", "Hair Studio"),
        ("HAIR SALON", "Hair Salon"),
        ("LASH STUDIO", "Lash Studio"),
        ("BROW BAR", "Brow Bar"),
    ],
    "Sports & Hobbies": [
        ("DECATHLON", "Decathlon"),
        ("ANYTIME FITNESS", "Anytime Fitness"),
        ("PURE FITNESS", "Pure Fitness"),
        ("VIRGIN ACTIVE", "Virgin Active"),
        ("FITNESS FIRST", "Fitness First"),
        ("GYMBOXX", "Gymboxx"),
        ("POPULAR BOOKSTORE", "Popular Bookstore"),
        ("KINOKUNIYA", "Kinokuniya"),
        ("TOYS R US", "Toys R Us"),
        ("SPORTS HUB", "Singapore Sports Hub"),
        ("ACTIVESG", "ActiveSG"),
        ("CLIMB CENTRAL", "Climb Central"),
        ("BADMINTON", "Badminton"),
        ("BOWLING", "Bowling"),
        ("YOGA", "Yoga Studio"),
        ("GYM", "Gym"),
    ],
    "Home": [
        ("IKEA", "IKEA"),
        ("HOME-FIX", "Home-Fix"),
        ("ACE HARDWARE", "Ace Hardware"),
        ("COURTS", "Courts"),
        ("HARVEY NORMAN", "Harvey Norman"),
        ("NITORI", "Nitori"),
        ("INDEX LIVING MALL", "Index Living Mall"),
        ("PEST CONTROL", "Pest Control"),
        ("AIRCON SERVICING", "Aircon Servicing"),
        ("HARDWARE", "Hardware Store"),
        ("FURNITURE", "Furniture"),
    ],
    "Healthcare": [
        ("RAFFLES MEDICAL", "Raffles Medical"),
        ("PARKWAY", "Parkway"),
        ("MOUNT ELIZABETH", "Mount Elizabeth Hospital"),
        ("SINGAPORE GENERAL HOSPITAL", "Singapore General Hospital"),
        ("TAN TOCK SENG", "Tan Tock Seng Hospital"),
        ("UNITY PHARMACY", "Unity Pharmacy"),
        ("SPECSAVERS", "Specsavers"),
        ("POLYCLINIC", "Polyclinic"),
        ("PHYSIOTHERAPY", "Physiotherapy"),
        ("OPTOMETRIST", "Optometrist"),
        ("DENTAL", "Dental Clinic"),
        ("DENTIST", "Dentist"),
        ("PHARMACY", "Pharmacy"),
        ("CLINIC", "Clinic"),
    ],
    "Education": [
        ("SKILLSFUTURE", "SkillsFuture"),
        ("COURSERA", "Coursera"),
        ("UDEMY", "Udemy"),
        ("BRITISH COUNCIL", "British Council"),
        ("MINDCHAMPS", "MindChamps"),
        ("KUMON", "Kumon"),
        ("MASTERCLASS", "MasterClass"),
        ("NTU", "Nanyang Technological University"),
        ("NUS", "National University of Singapore"),
        ("SMU", "Singapore Management University"),
        ("SUSS", "Singapore University of Social Sciences"),
        ("TUITION", "Tuition"),
        ("ENRICHMENT", "Enrichment Classes"),
    ],
}


def iter_default_rules() -> list[tuple[str, str, str]]:
    """Flatten DEFAULT_RULE_BANK into (match_pattern, target_category,
    display_label) tuples, longest match_pattern first so specific
    multi-word merchant names are checked before short generic keywords
    that could otherwise shadow them (e.g. "FINEST PAYA LEBAR QUARTER"
    before a hypothetical bare "FINEST")."""
    flat = [
        (pattern, category, label)
        for category, entries in DEFAULT_RULE_BANK.items()
        for pattern, label in entries
    ]
    flat.sort(key=lambda t: -len(t[0]))
    return flat
