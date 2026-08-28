"""Curated default categorization word bank - reconciled fresh into `rules`
on every app startup (see db.py::_reconcile_default_rules), so adding an
entry here reaches every existing DB without a one-off migration script.

Coverage comes from two tiers: (1) real merchant strings pulled from the
user's own historical UOB transactions, and (2) common Singapore
merchant/keyword knowledge for categories the real data didn't cover
(Beauty, Sports & Hobbies, Home, Healthcare, Education). This bank never
targets "Others"/"Other Income" or "Paynow"/"Paynow Received" - those are
pure fallback outcomes produced by the categorization engine itself
(engine/rules.py, engine/paynow.py), not rule matches. DEFAULT_PAYNOW_RULE_BANK
is a separate, lower-precedence tier for matching PayNow recipient names
(see its own docstring below).

Most entries below target an outflow category, but a handful (currently
"Refunds & Reimbursements" and "Investment Income") target an inflow one -
which category a pattern is allowed to fire for is entirely a property of
that category's `direction` in the categories table (see migrations.py),
not of which list it lives in here. engine/rules.py::categorize() enforces
the actual direction check at match time.
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
        ("LUCKINCOFFEE", "Luckin Coffee"),
        ("LUCKIN COFFEE", "Luckin Coffee"),
        ("YAMAZAKI", "Yamazaki"),
        ("GOKOKU", "Gokoku"),
        ("TAMAGO EN", "Tamago En"),
        ("CHICHA SAN CHEN", "Chicha San Chen"),
        ("ICHIKOKUDO", "Ichikokudo"),
        ("COCO ICHIBANYA", "CoCo Ichibanya"),
        ("NYLON COFFEE", "Nylon Coffee"),
        ("SONG FA", "Song Fa"),
        ("TORI-Q", "Tori-Q"),
        ("MESSINA", "Gelato Messina"),
        ("BROTHERBIRD", "Brotherbird"),
        ("TAMOYA UDON", "Tamoya Udon"),
        ("HUONG PHO", "Huong Pho"),
        ("APARTMENT COFFEE", "Apartment Coffee"),
        ("LAO HUO TANG", "Lao Huo Tang"),
        ("AVENUE CREAMERY", "Avenue Creamery"),
        ("EVERTON CREAMERY", "Everton Creamery"),
        ("YOLE", "Yolé"),
        ("FIELDNOTES", "Fieldnotes Coffee"),
        ("PASTAGO", "PastaGo"),
        ("MALA XIANG", "Mala Xiang Guo"),
        ("DAILY CHICKEN", "Daily Chicken"),
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
        # Chains and vending operators that showed up as "Others" in a
        # contributed statement - see docs/adding-a-bank.md's merchant-rules
        # issue template, which is where entries like these come from.
        ("MIXUE", "Mixue"),
        ("CHICK-FIL-A", "Chick-fil-A"),
        ("STUFF'D", "Stuff'd"),
        ("SANPOUTEI", "Sanpoutei Ramen"),
        ("GENKI SUSHI", "Genki Sushi"),
        ("SUSHIRO", "Sushiro"),
        ("TSUKIJI KAISENDON", "Tsukiji Kaisendon"),
        ("TSUKADA NOJO", "Tsukada Nojo"),
        ("YANG GUO FU", "Yang Guo Fu Mala Tang"),
        ("TAI ER", "Tai Er"),
        ("PAIKS", "Paik's Noodle"),
        ("THE RAMEN HOUSE", "The Ramen House"),
        ("PEPPERCORN MALA", "Peppercorn Mala"),
        ("AL-AMEEN", "Al-Ameen Eating House"),
        ("KIMLY", "Kimly"),
        ("ANNABELLA PATISSERIE", "Annabella Patisserie"),
        ("KODAWARI", "Kodawari Katsuya"),
        ("TOM'S PALETTE", "Tom's Palette"),
        ("SCOOT CAFE", "Scoot Cafe"),
        # Vending and beverage operators - the terminal name is the operator,
        # not the machine's location, so these match wherever the machine is.
        ("LE TACH VENDING", "Le Tach Vending"),
        ("ACHIEVA VENDING", "Achieva Vending"),
        ("COFFEEBOT", "Coffeebot"),
        ("COCA-COLA", "Coca-Cola"),
        ("YHS(SINGAPORE)", "Yeo Hiap Seng"),
        ("CHUAN SENG LEE", "Chuan Seng Lee Beverages"),
        ("KOPITIAM", "Kopitiam"),
        ("HAWKER", "Hawker Centre"),
    ],
    "Transport": [
        # From the user's real transaction history
        ("BUS/MRT", "Public Transport"),
        ("PARKING.SG", "Parking.sg"),
        ("CHARGESPOT", "ChargeSpot"),
        ("REFUEL.SG", "Refuel.sg"),
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
        ("MOBILE SUICA", "Mobile Suica"),
        ("GRAB", "Grab"),
    ],
    "Travel": [
        # Airbnb, Agoda and Scoot were the reason this category exists - they
        # had no honest home before it, and filing accommodation under
        # Entertainment would have put a wrong number on the dashboard rather
        # than an absent one.
        ("AIRBNB", "Airbnb"),
        ("AGODA", "Agoda"),
        ("BOOKING.COM", "Booking.com"),
        ("EXPEDIA", "Expedia"),
        ("TRIP.COM", "Trip.com"),
        ("HOTELS.COM", "Hotels.com"),
        ("KLOOK", "Klook"),
        ("TRAVELOKA", "Traveloka"),
        ("SKYSCANNER", "Skyscanner"),
        # Airlines. "FLYSCOOT" rather than a bare "SCOOT", which is a
        # substring of SCOOTER; the "SCOOT CAFE" line on a boarding pass is
        # food and stays Food & Drink, where its longer pattern wins anyway.
        ("SINGAPORE AIRLINES", "Singapore Airlines"),
        ("FLYSCOOT", "Scoot"),
        ("JETSTAR", "Jetstar"),
        ("AIRASIA", "AirAsia"),
        ("CATHAY PACIFIC", "Cathay Pacific"),
        ("MALAYSIA AIRLINES", "Malaysia Airlines"),
        ("BRITISH AIRWAYS", "British Airways"),
        ("EMIRATES", "Emirates"),
        ("QANTAS", "Qantas"),
        ("CHANGI AIRPORT", "Changi Airport"),
        # Hotel groups. No IBIS - it is a substring of HIBISCUS.
        ("MARRIOTT", "Marriott"),
        ("HILTON", "Hilton"),
        ("HYATT", "Hyatt"),
        ("SHANGRI-LA", "Shangri-La"),
        # Generic catch-alls, and genuinely last: iter_default_rules sorts
        # longest-first, so these only get a turn once every named merchant
        # above has missed.
        ("AIRLINES", "Airline"),
        ("AIRWAYS", "Airway"),
        ("HOTEL", "Hotel"),
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
        ("7-ELEVEN", "7-Eleven"),
        # Trailing space, so this can't fire on a longer word that merely
        # starts with "CHEERS" - every outlet prints as "CHEERS - <place>".
        ("CHEERS ", "Cheers"),
        ("SCARLETT", "Scarlett Supermarket"),
        ("KURIYA JAPANESE MKT", "Kuriya Japanese Market"),
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
        ("DAISO", "Daiso"),
        ("ALIEXPRESS", "AliExpress"),
        ("MARKS & SPENCER", "Marks & Spencer"),
    ],
    "Bills & Fees": [
        # From the user's real transaction history
        ("APPLE.COM/BILL", "Apple"),
        ("GOMO BY SINGTEL", "Gomo by Singtel"),
        ("GOMO MOBILE PLAN", "GOMO Mobile Plan"),
        ("MEMBERSHIP FEE", "Card Membership Fee"),
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
        ("INCOME INSURANCE", "Income Insurance"),
        ("MSIG", "MSIG"),
        ("AIA", "AIA"),
        ("M1 ", "M1"),
        # Insurance - general SG knowledge
        ("TOKIO MARINE", "Tokio Marine"),
        ("MANULIFE", "Manulife"),
        ("FWD SINGAPORE", "FWD"),
        ("ETIQA", "Etiqa"),
        ("HSBC LIFE", "HSBC Life"),
        ("SINGLIFE", "Singlife"),
        ("ALLIANZ", "Allianz"),
        ("INSURANCE", "Insurance"),
        # Taxes - from the user's real transaction history + general SG knowledge
        ("IRAS", "IRAS"),
        ("INCOME TAX", "Income Tax"),
        ("PROPERTY TAX", "Property Tax"),
        ("ROAD TAX", "Road Tax"),
    ],
    "Investing": [
        ("INTERACTIVE BROKERS", "Interactive Brokers"),
        ("TIGER BROKERS", "Tiger Brokers"),
        ("MOOMOO", "moomoo"),
        ("SAXO MARKETS", "Saxo Markets"),
        ("FSMONE", "FSMOne"),
        ("ENDOWUS", "Endowus"),
        ("STASHAWAY", "StashAway"),
        ("SYFE", "Syfe"),
        ("DBS VICKERS", "DBS Vickers"),
        ("UOB KAY HIAN", "UOB Kay Hian"),
        ("PHILLIP SECURITIES", "Phillip Securities"),
        ("CPF CASH TOP-UP", "CPF Cash Top-up"),
        ("SRS CONTRIBUTION", "SRS Contribution"),
    ],
    "Entertainment": [
        # From the user's real transaction history
        ("NETFLIX", "Netflix"),
        ("GARDENS BY THE BAY", "Gardens by the Bay"),
        ("SISTIC", "SISTIC"),
        ("DROPOUT.TV", "Dropout"),
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
        ("COW PLAY COW MOO", "Cow Play Cow Moo"),
        ("FUNCLAW", "Funclaw Amusement"),
        ("BLIZZARD ENTERTAINMENT", "Blizzard Entertainment"),
        # Golden Village prints as "GV <venue>", never as the full brand, so
        # the spelled-out rule above never fires on a real statement line.
        # Sorted last by length, after every longer pattern.
        ("GV ", "Golden Village"),
        ("MARINA BAY SANDS", "Marina Bay Sands"),
    ],
    "Beauty": [
        ("LE MANUCURE", "Le Manucure"),
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
        ("FIT BLOC", "Fit Bloc"),
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
    "Salary": [
        ("SALARY", "Salary"),
        ("PAYROLL", "Payroll"),
        ("GIRO SALARY", "Salary"),
        ("MONTHLY SALARY", "Salary"),
    ],
    # Inflow-direction categories - see this file's module docstring.
    "Refunds & Reimbursements": [
        ("REFUND", "Refund"),
        ("REVERSAL", "Reversal"),
        ("REIMBURSEMENT", "Reimbursement"),
        ("CASHBACK", "Cashback"),
        ("CASH BACK", "Cashback"),
    ],
    "Investment Income": [
        ("INTEREST CREDIT", "Bank Interest"),
        ("DIVIDEND", "Dividend"),
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
        ("NLB.GOV.SG", "National Library Board"),
        ("ENRICHMENT", "Enrichment Classes"),
    ],
}

# PayNow-transfer recipient names, kept separate from DEFAULT_RULE_BANK and
# always sorted after it (see iter_default_rules) - a PayNow line's "match
# text" is a free-text payee name off a person/company's PayNow registration
# rather than an established merchant brand, so it's inherently a shakier
# signal and must yield to every other default rule before it gets a turn.
DEFAULT_PAYNOW_RULE_BANK: list[tuple[str, str, str]] = [
    ("INTERACTIVE BR SG", "Investing", "Interactive Brokers"),
]


def _flatten_sorted(bank: dict[str, list[tuple[str, str]]] | list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    if isinstance(bank, dict):
        flat = [(pattern, category, label) for category, entries in bank.items() for pattern, label in entries]
    else:
        flat = list(bank)
    flat.sort(key=lambda t: -len(t[0]))
    return flat


def iter_default_rules() -> list[tuple[str, str, str]]:
    """Flatten DEFAULT_RULE_BANK into (match_pattern, target_category,
    display_label) tuples, longest match_pattern first so specific
    multi-word merchant names are checked before short generic keywords
    that could otherwise shadow them (e.g. "FINEST PAYA LEBAR QUARTER"
    before a hypothetical bare "FINEST"). DEFAULT_PAYNOW_RULE_BANK entries
    are appended after all of those, regardless of pattern length."""
    return _flatten_sorted(DEFAULT_RULE_BANK) + _flatten_sorted(DEFAULT_PAYNOW_RULE_BANK)
