import requests

def fetch_wikipedia_summary(name):
    # Step 1: Use the Search API to find the exact title
    search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={name}&format=json"
    search_response = requests.get(search_url)
    
    if search_response.status_code == 200:
        search_results = search_response.json().get("query", {}).get("search", [])
        
        if search_results:
            # Assume the first result is the most relevant one
            correct_title = search_results[0].get("title")
            print(f"Correct title found: {correct_title}")

            # Step 2: Use the correct title to fetch the summary
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{correct_title.replace(' ', '_')}"
            summary_response = requests.get(summary_url)
            
            if summary_response.status_code == 200:
                person_data = summary_response.json()
                return person_data  # or extract bio, image, etc. as needed
            else:
                print(f"Error fetching summary for title: {correct_title}")
        else:
            print("No search results found.")
    else:
        print("Error performing search request.")

    return None

# Example usage
name = "Shin Jeong-geun"#"Linghe Zhang"
person_data = fetch_wikipedia_summary(name)
if person_data:
    print("Person data fetched successfully:", person_data)
else:
    print("No data found for the person.")
