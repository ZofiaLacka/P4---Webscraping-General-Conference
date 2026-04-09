# Haley Chadwick, Monica Arias, Ashlyn Crop, Zofia Lacka
# P4 - General Conference Web Scraping Project
# This program scrapes General Conference talks, stores them in a Postgres database,
# and allows the user to view summary charts of scripture references.

from bs4 import BeautifulSoup
import requests
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import matplotlib.pyplot as plot


# -------------------------
# Scripture Dictionary Template
# All 87 books of LDS Standard Works plus spots for speaker, title, and kicker.
# We use .copy() inside the loop so each talk starts fresh with counts at zero.
# -------------------------
standard_works_template = {
    'Speaker_Name': '', 'Talk_Name': '', 'Kicker': '',
    'Matthew': 0, 'Mark': 0, 'Luke': 0, 'John': 0,
    'Acts': 0, 'Romans': 0, '1 Corinthians': 0, '2 Corinthians': 0,
    'Galatians': 0, 'Ephesians': 0, 'Philippians': 0, 'Colossians': 0,
    '1 Thessalonians': 0, '2 Thessalonians': 0, '1 Timothy': 0, '2 Timothy': 0,
    'Titus': 0, 'Philemon': 0, 'Hebrews': 0, 'James': 0,
    '1 Peter': 0, '2 Peter': 0, '1 John': 0, '2 John': 0, '3 John': 0,
    'Jude': 0, 'Revelation': 0, 'Genesis': 0, 'Exodus': 0,
    'Leviticus': 0, 'Numbers': 0, 'Deuteronomy': 0, 'Joshua': 0,
    'Judges': 0, 'Ruth': 0, '1 Samuel': 0, '2 Samuel': 0, '1 Kings': 0,
    '2 Kings': 0, '1 Chronicles': 0, '2 Chronicles': 0, 'Ezra': 0,
    'Nehemiah': 0, 'Esther': 0, 'Job': 0, 'Psalm': 0, 'Proverbs': 0,
    'Ecclesiastes': 0, 'Song of Solomon': 0, 'Isaiah': 0, 'Jeremiah': 0,
    'Lamentations': 0, 'Ezekiel': 0, 'Daniel': 0, 'Hosea': 0,
    'Joel': 0, 'Amos': 0, 'Obadiah': 0, 'Jonah': 0, 'Micah': 0,
    'Nahum': 0, 'Habakkuk': 0, 'Zephaniah': 0, 'Haggai': 0,
    'Zechariah': 0, 'Malachi': 0, '1 Nephi': 0, '2 Nephi': 0, 'Jacob': 0,
    'Enos': 0, 'Jarom': 0, 'Omni': 0, 'Words of Mormon': 0,
    'Mosiah': 0, 'Alma': 0, 'Helaman': 0, '3 Nephi': 0, '4 Nephi': 0,
    'Mormon': 0, 'Ether': 0, 'Moroni': 0, 'Doctrine and Covenants': 0,
    'Moses': 0, 'Abraham': 0, 'Joseph Smith—Matthew': 0,
    'Joseph Smith—History': 0, 'Articles of Faith': 0
}


# -------------------------
# Function One (Menu)
# Displays main menu and returns user choice
# -------------------------
def menu():
    print("\nMenu")
    print("1. Scrape General Conference Data")
    print("2. View Summaries")
    print("Any other key to exit")

    return input("Enter your choice: ")


# -------------------------
# Function Two (Scrape Data)
# Scrapes talks and saves them to Postgres
# -------------------------
def scrape_data(engine):

    # Drop table if it already exists so we don't get duplicate data
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS general_conference"))
        conn.commit()

    print("\nStarting scraping process...\n")

    # Load the main General Conference page that lists all talks
    url = "https://www.churchofjesuschrist.org/study/general-conference/2025/10?lang=eng"
    response = requests.get(url)

    # Stop if the main page could not be loaded
    if response.status_code != 200:
        print("Could not load the General Conference page.")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    base_url = "https://www.churchofjesuschrist.org"

    # Find all links that have an href attribute
    links = soup.select("a[href]")

    # Keep track of visited links so the same talk is not scraped twice
    visited_urls = set()

    for link in links:
        href = link.get("href")

        # Skip invalid links
        if href is None:
            continue

        # Only keep links related to general conference talks from 2025/10
        if "/study/general-conference/2025/10/" not in href:
            continue

        # Skip session overview pages (e.g. saturday-morning-session)
        if "session" in href.lower():
            continue

        # Build the full URL by adding the base domain to the relative link
        full_url = base_url + href if href.startswith("/") else href

        # Normalize the URL to avoid scraping the same talk twice
        full_url = full_url.split("?")[0] + "?lang=eng"

        # Skip duplicates
        if full_url in visited_urls:
            continue
        visited_urls.add(full_url)

        print(f"Trying to scrape url: {full_url}")

        # Load the individual talk page
        talk_response = requests.get(full_url)

        # Skip broken pages
        if talk_response.status_code != 200:
            print(f"  -> Skipping (bad status code: {talk_response.status_code})")
            continue

        talk_soup = BeautifulSoup(talk_response.text, "html.parser")

        # --- Get the talk title ---
        title = talk_soup.find("h1")
        if title is None:
            print(f"  -> Skipping (no title found)")
            continue
        title_text = title.text.strip()

        # Skip the "Sustaining of General Authorities" page - it is not a real talk
        if "Sustaining" in title_text:
            print(f"  -> Skipping (Sustaining page)")
            continue

        # Skip the "Introduction" page - it is not a real talk
        if "Introduction" in title_text:
            print(f"  -> Skipping (Introduction page)")
            continue

        # --- Get the speaker name ---
        # Try the most common class name first: "author-name"
        speaker = talk_soup.find("p", class_="author-name")

        # Some talks use a slightly different class, so try "author" as a fallback
        if speaker is None:
            speaker = talk_soup.find("p", class_="author")

        # If we still can't find it, try looking for any paragraph starting with "By "
        if speaker is None:
            speaker = talk_soup.find(lambda tag: tag.name == "p" and tag.text.strip().startswith("By "))

        # Extract the speaker text and remove the "By " prefix
        if speaker:
            speaker_text = speaker.text.strip()
            if speaker_text.startswith("By "):
                speaker_text = speaker_text[3:]
        else:
            # If we truly can't find a speaker, save a blank but still save the talk
            speaker_text = ""
            print(f"  -> Warning: no speaker found for {title_text}")

        # --- Get the kicker (opening quote before the talk begins) ---
        # The kicker is a <p> tag with class "kicker"
        kicker = talk_soup.find("p", class_="kicker")
        kicker_text = kicker.text.strip() if kicker else ""

        # --- Create a fresh copy of the scripture dictionary for this talk ---
        # Using .copy() makes sure each talk starts with all counts reset to zero
        data = standard_works_template.copy()

        # Store the basic talk info in the dictionary
        data["Speaker_Name"] = speaker_text
        data["Talk_Name"] = title_text
        data["Kicker"] = kicker_text

        # --- Count scripture references from the footnotes section ---
        # References are stored in a <footer> tag with class "notes"
        footnotes = talk_soup.find("footer", attrs={"class": "notes"})

        # Only count references if the talk has a footnotes section
        # (at least one talk has no references, so we must check for None)
        if footnotes is not None:
            footnotes_text = footnotes.text

            # Loop through every key and count how many times that book appears
            for key in data:
                if key not in ["Speaker_Name", "Talk_Name", "Kicker"]:
                    data[key] = footnotes_text.count(key)

        # Convert the dictionary to a one-row DataFrame and save to the database
        df = pd.DataFrame([data])
        df.to_sql("general_conference", engine, if_exists="append", index=False)

    print("\nYou've saved the scraped data to your postgres database.")


# -------------------------
# Function Three (Summary Menu)
# Displays second menu and returns user choice
# -------------------------
def summary_menu():
    return input("\nYou selected to see summaries. Enter 1 to see a summary of all talks. Enter 2 to select a specific talk. Enter anything else to exit: ")


# -------------------------
# Function Four (All Talks Summary)
# Shows a bar chart of scripture references across ALL talks combined
# Only shows books referenced more than 2 times
# -------------------------
def show_all_summary(engine):

    # Load all data from the database
    df = pd.read_sql("SELECT * FROM general_conference", engine)

    # Drop the text columns so we only have scripture reference counts left
    df = df.drop(columns=["Speaker_Name", "Talk_Name", "Kicker"])

    # Add up references for each book across all talks
    totals = df.sum()

    # Filter to only books that appear more than 2 times total
    totals = totals[totals > 2]

    # Plot the bar chart with the required title and axis labels
    totals.plot(kind="bar")
    plot.title("Standard Works Referenced in General Conference")
    plot.xlabel("Standard Works Books")
    plot.ylabel("# Times Referenced")
    plot.show()


# -------------------------
# Function Five (Single Talk Summary)
# Lets the user choose one talk by number and see its scripture reference chart
# Only shows books with at least 1 reference
# -------------------------
def show_single_talk(engine):

    # Load all data from the database
    df = pd.read_sql("SELECT * FROM general_conference", engine)

    # Filter out any rows where the speaker name is blank (bad scrape rows)
    df = df[df['Speaker_Name'] != '']

    # Reset the index so numbering is always clean starting from 1
    df = df.reset_index(drop=True)

    # Display all talks with a number so the user can pick one
    print("\nThe following are the names of speakers and their talks:")
    for index, row in df.iterrows():
        print(f"{index + 1}: {row['Speaker_Name']} - {row['Talk_Name']}")

    # Get the user's selection and handle bad input with try/except
    try:
        choice = int(input("\nPlease enter the number of the talk you want to see summarized: ")) - 1
    except ValueError:
        print("Invalid input. Please enter a number.")
        return

    # Make sure the number they entered actually matches a talk in the list
    if choice < 0 or choice >= len(df):
        print("That talk number does not exist.")
        return

    # Get the row for the selected talk using iloc (select by position)
    selected = df.iloc[choice]

    # Drop the text columns so only scripture counts remain
    data = selected.drop(labels=["Speaker_Name", "Talk_Name", "Kicker"])

    # Only show books that have at least 1 reference in this talk
    data = data[data > 0]

    # Plot the bar chart with the required title and axis labels
    data.plot(kind="bar")
    plot.title(f"Standard Works Referenced in: {selected['Talk_Name']}")
    plot.xlabel("Standard Works Books")
    plot.ylabel("# Times Referenced")
    plot.show()


# -------------------------
# Main Program
# Connects to the database and runs the menu loop
# -------------------------
def main():

    # Connect to the is303 Postgres database using your Mac username (no password needed)
    engine = sqlalchemy.create_engine(
        "postgresql://zofialacka@localhost:5432/is303"
    )

    # Keep showing the menu until the user chooses to exit
    while True:
        choice = menu()

        if choice == "1":
            scrape_data(engine)

        elif choice == "2":
            sub_choice = summary_menu()

            if sub_choice == "1":
                show_all_summary(engine)

            elif sub_choice == "2":
                show_single_talk(engine)

            else:
                print("Closing the program.")
                break

        else:
            print("Closing the program.")
            break


# Run the program
main()