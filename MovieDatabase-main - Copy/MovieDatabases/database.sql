-- Database schema for the Movie Database application

-- Create Person Table to store details of all individuals (directors, writers, actors)
CREATE TABLE Person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birthday TEXT,  -- Stores birthday in format "Month DD, YYYY"
    birthplace TEXT,  -- Stores birthplace from Wikipedia
    image_url TEXT,
    bio TEXT,
    wiki_url TEXT,
    last_updated TIMESTAMP
);

-- Create Movie Table with OMDb fields
CREATE TABLE Movie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    release_year TEXT NOT NULL,
    genre TEXT,
    rated TEXT,
    released TEXT,
    runtime TEXT,
    plot TEXT,
    language TEXT,
    country TEXT,
    awards TEXT,
    poster TEXT,
    imdbRating TEXT,
    imdbVotes TEXT,
    imdbID TEXT,
    type TEXT,
    totalSeasons TEXT,
    producer_id INTEGER,
    user_rating REAL,
    FOREIGN KEY (producer_id) REFERENCES Person(id)
);

-- Association Tables to link Movies and People by Role

-- MovieDirector table linking a movie to its directors
CREATE TABLE MovieDirector (
    movie_id INTEGER,
    person_id INTEGER,
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

-- MovieWriter table linking a movie to its writers
CREATE TABLE MovieWriter (
    movie_id INTEGER,
    person_id INTEGER,
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

-- MovieActor table linking a movie to its actors, with role information
CREATE TABLE MovieActor (
    movie_id INTEGER,
    person_id INTEGER,
    role TEXT,
    FOREIGN KEY (movie_id) REFERENCES Movie(id),
    FOREIGN KEY (person_id) REFERENCES Person(id)
);

