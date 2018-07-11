from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, SelectField
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt
from functools import wraps
import os.path

app = Flask(__name__)

photos = UploadSet('photos', IMAGES)

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'musicdb'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
# Secret key for Flask-WTF csrf_token
app.config['SECRET_KEY'] = 'secret123'
# Config photo uploads for album covers
app.config['UPLOADED_PHOTOS_DEST'] = 'static/album_art'
configure_uploads(app, photos)
# init MySQL
mysql = MySQL(app)


# Route for index page
@app.route('/')
def home():
    return render_template('index.html')

# Route for login page
@app.route('/login')
def login():
    return render_template('login.html')

# Route for the page that will display all entries in the database
@app.route('/view_all')
def view_all():
    # Create cursor
    cur = mysql.connection.cursor()

    # Get articles
    result = cur.execute("SELECT * FROM albums")

    albums = cur.fetchall()

    if result > 0:
        return render_template('view_all.html', albums=albums)
    else:
        msg = 'No Albums Found'
        return render_template('view_all.html', msg=msg)

    # Close DB connection
    cur.close()

@app.route('/view_album/<string:catno>/')
def view_album(catno):
    cur = mysql.connection.cursor()
    # Get the album from the 'albums' table
    result = cur.execute("SELECT * FROM albums WHERE catno = %s", [catno])

    album = cur.fetchone()
    # Get list of songs on the album from 'songs' table
    result_two = cur.execute("SELECT * FROM songs WHERE catno = %s", [catno])

    songs = cur.fetchall()

    cur.close()

    return render_template('view_album.html', album=album, songs=songs)

# Form for adding record to database
class AlbumForm(FlaskForm):
    # Album Art - figure out image uploads
    cover = FileField('Upload Cover Art')
    catno = StringField('Catalog Number')
    artist = StringField('Artist')
    title = StringField("Album Title")
    year = StringField('Year Released')
    rlabel = StringField('Record Label')
    genre = StringField('Genre')
    upc = StringField('UPC Code')
    format = SelectField(u'Album Format', choices=[('thirtythree', 'Vinyl, 33 1/3 RPM'), ('fortyfive', 'Vinyl, 45 RPM'), ('cass', 'Cassette')])

# Form for adding songs into DB
class SongForm(FlaskForm):
    trackno = StringField('Track Number')
    song_title = StringField('Title')
    minutes = StringField('MIN')
    seconds = StringField('SEC')

# Route for page that has a form to insert a new record into the database
@app.route('/add_album', methods=['GET', 'POST'])
def add_album():
    form = AlbumForm()
    if request.method == 'POST' and form.validate():
        # album art
        catno = form.catno.data.upper()
        artist = form.artist.data
        title = form.title.data
        year = form.year.data
        rlabel = form.rlabel.data
        genre = form.genre.data
        upc = form.upc.data
        format = form.format.data
        # format (lp or tape)

        # Create Cursor
        cur = mysql.connection.cursor()

        # Execute cursor
        cur.execute("INSERT INTO albums(catno, artist, title, year, rlabel, genre, format) VALUES(%s, %s, %s, %s, %s, %s, %s)",(catno, artist, title, year, rlabel, genre, format))

        # Commit to DB
        mysql.connection.commit()

        # Close DB connection
        cur.close()

        #flash('Repair Record Created', 'success')

        return redirect(url_for('view_all'))

    return render_template('add_album.html', form=form)

# Upload album cover art from edit page
@app.route('/upload_cover/<string:catno>', methods=['GET', 'POST'])
def upload_cover(catno):

    if request.method == 'POST' and 'photo' in request.files:
        # Get file from user
        file = request.files['photo']
        # Get the extention type from file
        ext = os.path.splitext(file.filename)[1]
        # Rename the file with the catalog number and file extension
        file.filename = catno.replace(" ", "") + ext
        # Save cover art
        photos.save(file)
        # Create Cursor
        cur = mysql.connection.cursor()
        # Execute cursor
        cur.execute("UPDATE albums SET albumArt=%s WHERE catno=%s", (file.filename, catno))
        # Commit to DB
        mysql.connection.commit()
        # Close DB connection
        cur.close()

        return redirect(url_for('view_album', catno=catno))

    return render_template('view_album.html')

# Edit album details
@app.route('/edit_album/<string:catno>/', methods=['GET', 'POST'])
def edit_album(catno):
    # Create Cursor
    cur = mysql.connection.cursor()

    # Get article by id
    result = cur.execute("SELECT * FROM albums WHERE catno = %s", [catno])

    album = cur.fetchone()

    # Get form
    form = AlbumForm(request.form)

    # Populate article form fields
    form.artist.data = album['artist']
    form.title.data = album['title']
    form.year.data = album['year']
    form.rlabel.data = album['rlabel']
    form.genre.data = album['genre']
    form.format.data = album['format']

    if request.method == 'POST' and form.validate():
        # cover =
        catno = album['catno']
        artist = request.form['artist']
        title = request.form['title']
        year = request.form['year']
        rlabel = request.form['rlabel']
        genre = request.form['genre']
        format = request.form['format']

        # Create Cursor
        cur = mysql.connection.cursor()
        # Execute cursor
        cur.execute("UPDATE albums SET artist=%s, title=%s, year=%s, rlabel=%s, genre=%s, format=%s WHERE catno=%s", (artist, title, year, rlabel, genre, format, catno))
        # Commit to DB
        mysql.connection.commit()
        # Close DB connection
        cur.close()

        flash('Album Updated', 'success')

        return redirect(url_for('view_album', catno=catno))

    return render_template('edit_album.html', album=album, form=form)

@app.route('/add_tracks/<string:catno>', methods=['GET', 'POST'])
def add_tracks(catno):

    # Create cursor
    cur = mysql.connection.cursor()
    # Get tracks for display as you're adding them
    result = cur.execute("SELECT * FROM songs WHERE catno=%s ORDER BY trackno ASC", [catno])

    songs = cur.fetchall()

    # Close DB connection
    cur.close()

    form = SongForm(request.form)

    if request.method == 'POST' and form.validate():
        catno = catno
        trackno = form.trackno.data
        title = form.song_title.data
        minutes = form.minutes.data
        seconds = form.seconds.data

        # Add colon between minutes and seconds to insert duration into DB
        duration = minutes + ":" + seconds

        cur = mysql.connection.cursor()

        cur.execute("INSERT INTO songs(catno, trackno, title, duration) VALUES(%s, %s, %s, %s)", (catno, trackno, title, duration))

        mysql.connection.commit()

        cur.close()

        return redirect(url_for('add_tracks', catno=catno))

    return render_template('add_tracks.html', songs=songs, form=form)

if __name__ == '__main__':
    app.run(debug=True)
