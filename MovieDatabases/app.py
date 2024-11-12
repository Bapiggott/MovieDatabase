import requests
from flask import Flask, request, render_template, request, g, redirect, url_for
import sqlite3

app = Flask(__name__)
DATABASE = 'database.db'
OMDB_API_KEY = 'e45abe68'  # Your OMDb API key

# Function to get a database connection
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row # Return rows as dictionaries for easier access
    return db

# Close the database connection at the end of each request
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/fetch_movie', methods=['GET', 'POST'])
def fetch_movie():
    if request.method == 'POST':
        title = request.form['title']
        release_year = request.form['release_year']
        user_rating = request.form.get('user_rating', type=float)  # Retrieve user rating

        # Fetch movie data from OMDb API
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&apikey={OMDB_API_KEY}'
        response = requests.get(omdb_url)
        movie_data = response.json()

        if movie_data.get('Response') == 'True':
            db = get_db()
            cur = db.cursor()
            
            # Insert movie data, including user rating
            cur.execute('''
                INSERT INTO Movie (title, release_year, genre, rated, released, runtime, plot, language, country,
                                   awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons, user_rating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                movie_data.get('Title'), movie_data.get('Year'), movie_data.get('Genre'), movie_data.get('Rated'),
                movie_data.get('Released'), movie_data.get('Runtime'), movie_data.get('Plot'),
                movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
                movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'),
                movie_data.get('imdbID'), movie_data.get('Type'), movie_data.get('totalSeasons'), user_rating
            ))
            movie_id = cur.lastrowid  # Get the ID of the inserted movie

            # Process directors
            for director_name in movie_data.get('Director', '').split(', '):
                if director_name:
                    director_id = add_person_if_not_exists(db, director_name)
                    cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, director_id))

            # Process writers
            for writer_name in movie_data.get('Writer', '').split(', '):
                if writer_name:
                    writer_id = add_person_if_not_exists(db, writer_name)
                    cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, writer_id))

            # Process actors
            for actor_name in movie_data.get('Actors', '').split(', '):
                if actor_name:
                    actor_id = add_person_if_not_exists(db, actor_name)
                    cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, actor_id, "Actor"))

            db.commit()
            return redirect(url_for('index'))
        else:
            return f"Movie not found: {movie_data.get('Error')}", 404

    return render_template('fetch_movie.html')




@app.route('/update_movies', methods=['GET'])
def update_movies():
    db = get_db()
    cur = db.cursor()
    
    # Fetch all movies from the database
    cur.execute('SELECT id, title, release_year FROM Movie')
    movies = cur.fetchall()

    # Loop through each movie and update its data
    for movie in movies:
        movie_id, title, release_year = movie

        # Fetch updated data from OMDb API
        omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&apikey={OMDB_API_KEY}'
        response = requests.get(omdb_url)
        movie_data = response.json()

        if movie_data.get('Response') == 'True':
            # Update movie data in the database
            cur.execute('''
                UPDATE Movie
                SET genre = ?, rated = ?, released = ?, runtime = ?, plot = ?, language = ?, country = ?,
                    awards = ?, poster = ?, imdbRating = ?, imdbVotes = ?, imdbID = ?, type = ?, totalSeasons = ?
                WHERE id = ?
            ''', (
                movie_data.get('Genre'), movie_data.get('Rated'), movie_data.get('Released'), movie_data.get('Runtime'),
                movie_data.get('Plot'), movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
                movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'), movie_data.get('imdbID'),
                movie_data.get('Type'), movie_data.get('totalSeasons'), movie_id
            ))

            # Clear existing associations for directors, writers, and actors
            cur.execute('DELETE FROM MovieDirector WHERE movie_id = ?', (movie_id,))
            cur.execute('DELETE FROM MovieWriter WHERE movie_id = ?', (movie_id,))
            cur.execute('DELETE FROM MovieActor WHERE movie_id = ?', (movie_id,))

            # Update directors
            for director_name in movie_data.get('Director', '').split(', '):
                if director_name:
                    director_id = add_person_if_not_exists(db, director_name)
                    cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, director_id))

            # Update writers
            for writer_name in movie_data.get('Writer', '').split(', '):
                if writer_name:
                    writer_id = add_person_if_not_exists(db, writer_name)
                    cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, writer_id))

            # Update actors
            for actor_name in movie_data.get('Actors', '').split(', '):
                if actor_name:
                    actor_id = add_person_if_not_exists(db, actor_name)
                    cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, actor_id, "Actor"))

    # Commit all updates to the database
    db.commit()
    return "Movies and associated people updated successfully!"



@app.route('/update_individual_movie/<int:movie_id>', methods=['GET'])
def update_individual_movie(movie_id):
    db = get_db()
    cur = db.cursor()
    
    # Fetch the specific movie from the database based on movie_id
    cur.execute('SELECT id, title, release_year FROM Movie WHERE id = ?', (movie_id,))
    movie = cur.fetchone()  # fetchone() retrieves a single row without needing an argument

    if movie is None:
        return "Movie not found", 404

    movie_id, title, release_year = movie

    # Fetch updated data from OMDb API
    omdb_url = f'http://www.omdbapi.com/?t={title}&y={release_year}&apikey={OMDB_API_KEY}'
    response = requests.get(omdb_url)
    movie_data = response.json()

    if movie_data.get('Response') == 'True':
        # Update movie data in the database
        cur.execute('''
            UPDATE Movie
            SET genre = ?, rated = ?, released = ?, runtime = ?, plot = ?, language = ?, country = ?,
                awards = ?, poster = ?, imdbRating = ?, imdbVotes = ?, imdbID = ?, type = ?, totalSeasons = ?
            WHERE id = ?
        ''', (
            movie_data.get('Genre'), movie_data.get('Rated'), movie_data.get('Released'), movie_data.get('Runtime'),
            movie_data.get('Plot'), movie_data.get('Language'), movie_data.get('Country'), movie_data.get('Awards'),
            movie_data.get('Poster'), movie_data.get('imdbRating'), movie_data.get('imdbVotes'), movie_data.get('imdbID'),
            movie_data.get('Type'), movie_data.get('totalSeasons'), movie_id
        ))

        # Clear existing associations for directors, writers, and actors
        cur.execute('DELETE FROM MovieDirector WHERE movie_id = ?', (movie_id,))
        cur.execute('DELETE FROM MovieWriter WHERE movie_id = ?', (movie_id,))
        cur.execute('DELETE FROM MovieActor WHERE movie_id = ?', (movie_id,))

        # Update directors
        for director_name in movie_data.get('Director', '').split(', '):
            if director_name:
                director_id = add_person_if_not_exists(db, director_name)
                cur.execute('INSERT INTO MovieDirector (movie_id, person_id) VALUES (?, ?)', (movie_id, director_id))

        # Update writers
        for writer_name in movie_data.get('Writer', '').split(', '):
            if writer_name:
                writer_id = add_person_if_not_exists(db, writer_name)
                cur.execute('INSERT INTO MovieWriter (movie_id, person_id) VALUES (?, ?)', (movie_id, writer_id))

        # Update actors
        for actor_name in movie_data.get('Actors', '').split(', '):
            if actor_name:
                actor_id = add_person_if_not_exists(db, actor_name)
                cur.execute('INSERT INTO MovieActor (movie_id, person_id, role) VALUES (?, ?, ?)', (movie_id, actor_id, "Actor"))

    # Commit all updates to the database
    db.commit()
    return "Movie and associated people updated successfully!"


"""@app.route('/')
def index():
    sort_by = request.args.get('sort_by', 'title')  # Default sort by 'title'
    order = request.args.get('order', 'asc')  # Default order is ascending

    # Ensure sort_by is one of the allowed fields to prevent SQL injection
    allowed_fields = ['title', 'release_year', 'genre', 'rated', 'imdbRating']
    if sort_by not in allowed_fields:
        sort_by = 'title'

    # Toggle order for the next click
    new_order = 'desc' if order == 'asc' else 'asc'

    db = get_db()
    cur = db.cursor()

    # Use SUBSTR to get the first year in case of ranges (e.g., 2019–2020)
    if sort_by == 'release_year':
        query = f'''
            SELECT id, title, SUBSTR(release_year, 1, 4) AS release_year, genre, rated, imdbRating,
                   director, writer, actors
            FROM Movie
            ORDER BY release_year {order}
        '''
    else:
        query = f'''
            SELECT id, title, release_year, genre, rated, imdbRating,
                   director, writer, actors
            FROM Movie
            ORDER BY {sort_by} {order}
        '''

    cur.execute(query)
    movies = cur.fetchall()
    return render_template('index.html', movies=movies, sort_by=sort_by, new_order=new_order)
"""
@app.route('/')
def index():
    sort_by = request.args.get('sort_by', 'title')  # Default to 'title'
    order = request.args.get('order', 'asc')  # Default order is ascending
    new_order = 'desc' if order == 'asc' else 'asc'

    # Ensure sort_by is one of the allowed fields to prevent SQL injection
    allowed_fields = ['title', 'release_year', 'genre', 'rated', 'imdbRating', 'country', 'user_rating']
    sort_by = sort_by if sort_by in allowed_fields else 'title'
    order = order if order in ['asc', 'desc'] else 'asc'

    db = get_db()
    cur = db.cursor()

    # Build query based on whether sorting by release_year or another field
    if sort_by == 'release_year':
        query = f'''
            SELECT 
                Movie.id, 
                Movie.title, 
                SUBSTR(Movie.release_year, 1, 4) AS release_year, 
                Movie.genre, 
                Movie.rated, 
                Movie.imdbRating,
                Movie.country,
                Movie.user_rating,
                GROUP_CONCAT(DISTINCT PersonDirector.name) AS director,
                GROUP_CONCAT(DISTINCT PersonWriter.name) AS writer,
                GROUP_CONCAT(DISTINCT PersonActor.name) AS actors
            FROM Movie
            LEFT JOIN MovieDirector ON Movie.id = MovieDirector.movie_id
            LEFT JOIN Person AS PersonDirector ON MovieDirector.person_id = PersonDirector.id
            LEFT JOIN MovieWriter ON Movie.id = MovieWriter.movie_id
            LEFT JOIN Person AS PersonWriter ON MovieWriter.person_id = PersonWriter.id
            LEFT JOIN MovieActor ON Movie.id = MovieActor.movie_id
            LEFT JOIN Person AS PersonActor ON MovieActor.person_id = PersonActor.id
            GROUP BY Movie.id
            ORDER BY SUBSTR(Movie.release_year, 1, 4) {order}
        '''
    else:
        query = f'''
            SELECT 
                Movie.id, 
                Movie.title, 
                Movie.release_year, 
                Movie.genre, 
                Movie.rated, 
                Movie.imdbRating,
                Movie.country,
                Movie.user_rating,
                GROUP_CONCAT(DISTINCT PersonDirector.name) AS director,
                GROUP_CONCAT(DISTINCT PersonWriter.name) AS writer,
                GROUP_CONCAT(DISTINCT PersonActor.name) AS actors
            FROM Movie
            LEFT JOIN MovieDirector ON Movie.id = MovieDirector.movie_id
            LEFT JOIN Person AS PersonDirector ON MovieDirector.person_id = PersonDirector.id
            LEFT JOIN MovieWriter ON Movie.id = MovieWriter.movie_id
            LEFT JOIN Person AS PersonWriter ON MovieWriter.person_id = PersonWriter.id
            LEFT JOIN MovieActor ON Movie.id = MovieActor.movie_id
            LEFT JOIN Person AS PersonActor ON MovieActor.person_id = PersonActor.id
            GROUP BY Movie.id
            ORDER BY {sort_by} {order}
        '''
    
    # Execute the query
    cur.execute(query)
    movies = cur.fetchall()

    return render_template('index.html', movies=movies, sort_by=sort_by, order=order, new_order=new_order)



"""# Route to display detailed information about a single movie
@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT title, release_year, genre, rated, released, runtime, plot, language, country, awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons, director, writer, actors FROM Movie WHERE id = ?', (movie_id,))
    movie = cur.fetchone()
    return render_template('movie_detail.html', movie=movie)"""


@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    db = get_db()
    cur = db.cursor()

    # Fetch movie details
    cur.execute('''
        SELECT title, release_year, genre, rated, released, runtime, plot, language, country, awards, poster, imdbRating, imdbVotes, imdbID, type, totalSeasons
        FROM Movie WHERE id = ?
    ''', (movie_id,))
    movie = cur.fetchone()

    # Fetch directors associated with this movie
    cur.execute('''
        SELECT Person.id, Person.name FROM MovieDirector
        JOIN Person ON MovieDirector.person_id = Person.id
        WHERE MovieDirector.movie_id = ?
    ''', (movie_id,))
    directors = cur.fetchall()

    # Fetch writers associated with this movie
    cur.execute('''
        SELECT Person.id, Person.name FROM MovieWriter
        JOIN Person ON MovieWriter.person_id = Person.id
        WHERE MovieWriter.movie_id = ?
    ''', (movie_id,))
    writers = cur.fetchall()

    # Fetch actors associated with this movie, including their roles
    cur.execute('''
        SELECT Person.id, Person.name, MovieActor.role FROM MovieActor
        JOIN Person ON MovieActor.person_id = Person.id
        WHERE MovieActor.movie_id = ?
    ''', (movie_id,))
    actors = cur.fetchall()

    return render_template('movie_detail.html', movie_id=movie_id, movie=movie, directors=directors, writers=writers, actors=actors)


@app.route('/person/<int:person_id>')
def person_detail(person_id):
    db = get_db()
    cur = db.cursor()
    
    # Retrieve person details directly from the database
    cur.execute('SELECT name, birthday, image_url, bio FROM Person WHERE id = ?', (person_id,))
    person = cur.fetchone()
    if person is None:
        return "Person not found", 404
    name, birthday, image_url, bio = person

    # Get all movies associated with this person
    cur.execute('''
        SELECT Movie.id, Movie.title, 'Director' AS role FROM MovieDirector
        JOIN Movie ON MovieDirector.movie_id = Movie.id
        WHERE MovieDirector.person_id = ?
        UNION
        SELECT Movie.id, Movie.title, 'Writer' AS role FROM MovieWriter
        JOIN Movie ON MovieWriter.movie_id = Movie.id
        WHERE MovieWriter.person_id = ?
        UNION
        SELECT Movie.id, Movie.title, MovieActor.role FROM MovieActor
        JOIN Movie ON MovieActor.movie_id = Movie.id
        WHERE MovieActor.person_id = ?
    ''', (person_id, person_id, person_id))
    movies = cur.fetchall()

    return render_template('person_detail.html', person_id=person_id, name=name, birthday=birthday, image_url=image_url, bio=bio, movies=movies)


def add_person_if_not_exists(db, name):
    cur = db.cursor()
    cur.execute('SELECT id FROM Person WHERE name = ?', (name,))
    person = cur.fetchone()
    
    # If person exists, return their ID
    if person:
        return person[0]

    # Fetch additional details for the new person using the fetch_person_data helper
    bio, image_url, birthday, birthplace = fetch_person_data(name)

    # Insert the new person with fetched details into the database
    cur.execute('''
        INSERT INTO Person (name, birthday, birthplace, image_url, bio)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, birthday, birthplace, image_url, bio))
    db.commit()

    return cur.lastrowid  # Return the new person ID



@app.route('/update_rating/<int:movie_id>', methods=['POST'])
def update_rating(movie_id):
    user_rating = request.form.get('user_rating', type=float)
    sort_by = request.form.get('sort_by', 'title')  # Default to 'title' if not provided
    order = request.form.get('order', 'asc')  # Default to 'asc' if not provided

    db = get_db()
    cur = db.cursor()
    
    # Update the user rating for the specified movie
    cur.execute('UPDATE Movie SET user_rating = ? WHERE id = ?', (user_rating, movie_id))
    db.commit()
    
    # Redirect to index with the same sorting parameters
    return redirect(url_for('index', sort_by=sort_by, order=order))



def fetch_person_data(name):
    """Fetch bio, image, birthday, and birthplace from Wikipedia for a given name."""
    bio, image_url, birthday, birthplace = None, None, None, None
    person_data = {}  # Initialize to avoid UnboundLocalError
    profession_keywords = ["actor", "actress", "singer", "director", "writer"]

    # Attempt to fetch the Wikipedia page summary for the person
    base_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
    response = requests.get(base_url)

    if response.status_code != 200:
        # Try search API if the initial request fails
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={name}&format=json"
        search_response = requests.get(search_url)
        
        if search_response.status_code == 200:
            search_results = search_response.json().get("query", {}).get("search", [])
            relevant_topic = None
            
            # Search through titles and snippets for relevant profession
            for priority in profession_keywords:
                for result in search_results:
                    title = result.get("title", "").lower()
                    snippet = result.get("snippet", "").lower()
                    if priority in title or priority in snippet:
                        relevant_topic = result.get("title")
                        break
                if relevant_topic:
                    break

            # Fetch specific summary if a relevant topic was found
            if relevant_topic:
                specific_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{relevant_topic.replace(' ', '_')}"
                specific_response = requests.get(specific_url)

                if specific_response.status_code == 200:
                    person_data = specific_response.json()
                    bio = person_data.get("extract")
                    image_url = person_data.get("thumbnail", {}).get("source")
    else:
        # Process successful summary response
        person_data = response.json()
        if person_data.get("type") == "disambiguation":
            # Disambiguation logic as in the previous function
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={name}&format=json"
            search_response = requests.get(search_url)
            if search_response.status_code == 200:
                search_results = search_response.json().get("query", {}).get("search", [])
                relevant_topic = None
                for priority in profession_keywords:
                    for result in search_results:
                        title = result.get("title", "").lower()
                        snippet = result.get("snippet", "").lower()
                        if priority in title or priority in snippet:
                            relevant_topic = result.get("title")
                            break
                    if relevant_topic:
                        break
                if relevant_topic:
                    specific_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{relevant_topic.replace(' ', '_')}"
                    specific_response = requests.get(specific_url)
                    if specific_response.status_code == 200:
                        person_data = specific_response.json()
                        bio = person_data.get("extract")
                        image_url = person_data.get("thumbnail", {}).get("source")
        else:
            bio = person_data.get("extract")
            image_url = person_data.get("thumbnail", {}).get("source")

    # Extract birthday and birthplace if they exist in description
    # full_birthday_info = person_data.get("description")
    print(person_data)
    birthday =  person_data.get("description")
    """if full_birthday_info:
        try:
            birthday_part = full_birthday_info.split(" (age ")[0].strip()
            birthplace_part = full_birthday_info.split(")")[1].strip()
            birthday = birthday_part
            birthplace = birthplace_part
        except (IndexError, ValueError):
            print("Could not parse birthday and birthplace separately.")"""

    return bio, image_url, birthday, birthplace


@app.route('/update_individual_person/<int:person_id>')
def update_individual_person(person_id):
    db = get_db()
    cur = db.cursor()
    
    # Fetch person details with missing data in the Person table for the given person_id
    cur.execute('SELECT id, name FROM Person WHERE (birthday IS NULL OR image_url IS NULL OR bio IS NULL) AND id = ?', (person_id,))
    person = cur.fetchone()

    if person is None:
        return "Person not found or already has complete data", 404

    person_id, name = person
    print(f"Fetching data for {name} with ID {person_id}")

    # Fetch data from Wikipedia
    bio, image_url, birthday, birthplace = fetch_person_data(name)

    # Update the Person table with the fetched details
    cur.execute('''
        UPDATE Person
        SET birthday = COALESCE(?, birthday),
            birthplace = COALESCE(?, birthplace),
            image_url = COALESCE(?, image_url),
            bio = COALESCE(?, bio)
        WHERE id = ?
    ''', (birthday, birthplace, image_url, bio, person_id))
    db.commit()
    print("Person data updated successfully in the database.")

    # Verify update by querying the database again
    cur.execute('SELECT bio, image_url, birthday, birthplace FROM Person WHERE id = ?', (person_id,))
    updated_person = cur.fetchone()
    print("Updated record in database:", updated_person)

    return "Person data updated successfully!"


@app.route('/update_people_data')
def update_people_data():
    db = get_db()
    cur = db.cursor()
    
    # Fetch all people with missing data in the Person table
    cur.execute('SELECT id, name FROM Person WHERE birthday IS NULL OR image_url IS NULL OR bio IS NULL')
    people = cur.fetchall()

    for person_id, name in people:
        print(f"Fetching data for {name} with ID {person_id}")

        # Fetch data from Wikipedia
        bio, image_url, birthday, birthplace = fetch_person_data(name)

        # Update the Person table with the fetched details if found
        cur.execute('''
            UPDATE Person
            SET birthday = COALESCE(?, birthday),
                birthplace = COALESCE(?, birthplace),
                image_url = COALESCE(?, image_url),
                bio = COALESCE(?, bio)
            WHERE id = ?
        ''', (birthday, birthplace, image_url, bio, person_id))
        db.commit()

        # Verify the update by querying the database again
        cur.execute('SELECT bio, image_url, birthday, birthplace FROM Person WHERE id = ?', (person_id,))
        updated_person = cur.fetchone()
        print(f"Updated record in database for {name}:", updated_person)

    return "People data updated successfully!"




if __name__ == '__main__':
    app.run(debug=True)
