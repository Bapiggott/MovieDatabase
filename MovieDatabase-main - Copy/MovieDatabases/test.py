import requests
import re

"""
This module handles Wikipedia data extraction for movie-related people (actors, directors, etc.).
It uses Wikipedia's API to fetch and parse biographical information.
Key features:
- Extracts bio, birthday, birthplace, and image from Wikipedia
- Handles multiple date formats used in Wikipedia
- Cleans up wiki markup from extracted text
"""

def fetch_wikipedia_summary(name):
    """
    Main function to extract person data from Wikipedia.
    Process:
    1. Search Wikipedia for the person
    2. Get the page content
    3. Extract birthday using multiple patterns
    4. Extract birthplace
    5. Get bio and image from summary API
    """
    bio, image_url, birthday, birthplace = None, None, None, None

    # Step 1: Use the Search API to find the exact title
    search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={name}&format=json"
    search_response = requests.get(search_url)
    
    if search_response.status_code == 200:
        search_results = search_response.json().get("query", {}).get("search", [])
        
        if search_results:
            correct_title = search_results[0].get("title")
            print(f"Correct title found: {correct_title}")

            # Step 2: Get the page content
            content_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={correct_title.replace(' ', '_')}&prop=revisions&rvprop=content&format=json&formatversion=2"
            content_response = requests.get(content_url)
            
            if content_response.status_code == 200:
                page_content = content_response.json()
                pages = page_content.get('query', {}).get('pages', [])
                if pages:
                    content = pages[0].get('revisions', [{}])[0].get('content', '')
                    
                    # List of patterns to match various Wikipedia date formats:
                    # - {{birth date|YYYY|MM|DD}}
                    # - {{birth date and age|YYYY|MM|DD}}
                    # - YYYY-MM-DD
                    # - DD Month YYYY
                    # - Month DD, YYYY
                    # etc.
                    birth_patterns = [
                        r"\|\s*birth_date\s*=\s*{{birth date(?:\|df=y)?\|(\d{4})\|(\d{1,2})\|(\d{1,2})}}",
                        r"\|\s*birth_date\s*=\s*{{birth\s*date\s*and\s*age\|(\d{4})\|(\d{1,2})\|(\d{1,2})}}",
                        r"\|\s*birth_date\s*=\s*(\d{4})-(\d{2})-(\d{2})",
                        r"\|\s*birth_date\s*=\s*(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
                        r"\|\s*birth_date\s*=\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
                        r"\|\s*birth_date\s*=\s*{{dob\|(\d{4})\|(\d{1,2})\|(\d{1,2})}}",
                        r"\|\s*birth_date\s*=\s*{{birth-date\|(\d{1,2})\|(\d{1,2})\|(\d{4})}}",
                        r"\|\s*birth_date\s*=\s*{{birth year and age\|(\d{4})}}",
                        r"\|\s*birth_date\s*=\s*{{Birth date\|(\d{4})\|(\d{1,2})\|(\d{1,2})}}",
                        r"\|\s*birth_date\s*=\s*{{BirthDeathAge\|[^|]*\|(\d{4})\|(\d{1,2})\|(\d{1,2})}}",
                        r"\|\s*birth\s*=\s*{{birth date\|(\d{4})\|(\d{1,2})\|(\d{1,2})}}",
                        r"\|\s*birth\s*=\s*(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
                        r"born\s+(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
                        r"born\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
                    ]
                    
                    months = ['January', 'February', 'March', 'April', 'May', 'June', 
                            'July', 'August', 'September', 'October', 'November', 'December']
                    
                    for pattern in birth_patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            groups = match.groups()
                            if len(groups) == 3:
                                if groups[0] in months:
                                    # Format: Month DD YYYY
                                    month = groups[0]
                                    day = int(groups[1])
                                    year = groups[2]
                                elif groups[1] in months:
                                    # Format: DD Month YYYY
                                    day = int(groups[0])
                                    month = groups[1]
                                    year = groups[2]
                                else:
                                    # Format: YYYY MM DD
                                    year = groups[0]
                                    month = months[int(groups[1])-1]
                                    day = int(groups[2])
                                
                                birthday = f"{month} {day}, {year}"
                                break
                    
                    # After trying the patterns, add this section for better fallback handling:
                    if not birthday:
                        # Try to find date in the content text
                        date_patterns = [
                            r"born\s+(?:on\s+)?(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
                            r"born\s+(?:on\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
                            r"\[\[(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\]\]"
                        ]
                        
                        for pattern in date_patterns:
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                groups = match.groups()
                                if groups[1] in months:  # DD Month YYYY
                                    day = int(groups[0])
                                    month = groups[1]
                                    year = groups[2]
                                else:  # Month DD YYYY
                                    month = groups[0]
                                    day = int(groups[1])
                                    year = groups[2]
                                birthday = f"{month} {day}, {year}"
                                break

                        if not birthday:
                            # Try to find just the year
                            year_patterns = [
                                r"\|\s*birth_year\s*=\s*(\d{4})",
                                r"born\s+in\s+(\d{4})",
                                r"\(\s*born\s+(?:in\s+)?(\d{4})\s*\)",
                                r"\[\[(\d{4})\]\]\s*births",
                            ]
                            
                            for pattern in year_patterns:
                                year_match = re.search(pattern, content, re.IGNORECASE)
                                if year_match:
                                    year = year_match.group(1)
                                    birthday = f"Unknown Date, {year}"
                                    break

                    # Add this at the end of the function to clean up any remaining wiki markup
                    if birthday:
                        birthday = re.sub(r'\[\[([^|\]]*?)(?:\|[^\]]*?)?\]\]', r'\1', birthday)  # Clean wiki links
                        birthday = re.sub(r'[\[\]{}]', '', birthday)  # Remove remaining brackets
                        birthday = birthday.strip()
                    
                    # Patterns to extract birthplace from different Wikipedia infobox formats
                    birthplace_patterns = [
                        r"\|\s*birth_place\s*=\s*([^|\n{]+)",
                        r"\|\s*birthplace\s*=\s*([^|\n{]+)",
                        r"\|\s*placeofbirth\s*=\s*([^|\n{]+)"
                    ]
                    
                    for pattern in birthplace_patterns:
                        birthplace_match = re.search(pattern, content, re.IGNORECASE)
                        if birthplace_match:
                            birthplace = birthplace_match.group(1).strip()
                            # Clean up birthplace text
                            birthplace = re.sub(r'\[\[([^|\]]*?)(?:\|[^\]]*?)?\]\]', r'\1', birthplace)  # Handle wiki links
                            birthplace = re.sub(r'[\[\]{}]', '', birthplace)  # Remove remaining brackets
                            birthplace = re.sub(r'<[^>]+>', '', birthplace)   # Remove HTML tags
                            birthplace = re.sub(r'\s+', ' ', birthplace)      # Normalize whitespace
                            birthplace = birthplace.strip()
                            break

            # Step 3: Get the summary and image
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{correct_title.replace(' ', '_')}"
            summary_response = requests.get(summary_url)
            
            if summary_response.status_code == 200:
                summary_data = summary_response.json()
                bio = summary_data.get('extract')
                image_url = summary_data.get('thumbnail', {}).get('source')
                
                # If we got a larger thumbnail, get the original image
                if image_url:
                    image_url = image_url.replace('/thumb/', '/').split('/')
                    image_url = '/'.join(image_url[:-1])  # Remove the thumbnail size specification

    return bio, image_url, birthday, birthplace

def test_fetch_person_data():
    test_names = [
        "Hyun Bin",
        "Son Ye-jin",
        "Tom Cruise",
        "Steven Spielberg",
        "Song Joong-ki",
        "Park Seo-joon",
        "Sam Neill",
        "Morgan Freeman",
        "Anthony Hopkins",
        "Helen Mirren"
    ]
    
    for name in test_names:
        print(f"\nTesting fetch for: {name}")
        bio, image_url, birthday, birthplace = fetch_wikipedia_summary(name)
        print(f"Birthday: {birthday}")
        print(f"Birthplace: {birthplace}")
        print(f"Has image: {'Yes' if image_url else 'No'}")
        print(f"Bio length: {len(bio) if bio else 0}")

if __name__ == "__main__":
    test_fetch_person_data()
