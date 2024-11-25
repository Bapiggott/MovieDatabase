import sqlite3

def cleanup_duplicates():
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    
    print("Starting cleanup...")
    
    # Get all duplicate movies
    cur.execute('''
        SELECT title, release_year, COUNT(*) as count
        FROM Movie
        GROUP BY title, release_year
        HAVING count > 1
    ''')
    duplicates = cur.fetchall()
    
    for title, year, count in duplicates:
        print(f"Found {count} duplicates for {title} ({year})")
        
        # Get the first (primary) movie ID to keep
        cur.execute('''
            SELECT id FROM Movie 
            WHERE title = ? AND release_year = ? 
            LIMIT 1
        ''', (title, year))
        primary_id = cur.fetchone()[0]
        
        # Delete duplicate entries but keep associations
        cur.execute('''
            DELETE FROM Movie 
            WHERE title = ? AND release_year = ? 
            AND id != ?
        ''', (title, year, primary_id))
        
        print(f"Cleaned up duplicates for {title}")
    
    conn.commit()
    conn.close()
    print("Database cleaned of duplicates!")

if __name__ == '__main__':
    cleanup_duplicates() 