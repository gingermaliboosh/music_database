from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, PasswordField, validators
from flask_uploads import UploadSet, configure_uploads, IMAGES, patch_request_class
from werkzeug.utils import secure_filename
from passlib.hash import sha256_crypt
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
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
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])
# init MySQL
mysql = MySQL(app)
# Config SQLAlchemy. Used for pagination when viewing all albums
app.config['SQLALCHEMY_DATABASE_URI'] ='mysql://root:root@localhost/musicdb'
db = SQLAlchemy(app)

# Form for registering
class RegisterForm(FlaskForm):
    username = StringField('Username', [validators.DataRequired(), validators.Length(min=4, max=25)])
    password = PasswordField('Password', [validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')

# Form for adding record to database
class AlbumForm(FlaskForm):
    # Album Art - figure out image uploads
    cover = FileField(validators=[FileAllowed(photos, u'Image only!'), FileRequired(u'File was empty!')])
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

class Albums(db.Model):
    __tablename__ = 'albums'
    id = db.Column('id', db.Integer, primary_key=True)
    albumArt = db.Column('albumArt', db.Unicode)
    catno = db.Column('catno', db.Unicode)
    artist = db.Column('artist', db.Unicode)
    title = db.Column('title', db.Unicode)
    year = db.Column('year', db.Integer)
    rlabel = db.Column('rlabel', db.Unicode)
    genre = db.Column('genre', db.Unicode)
    upc = db.Column('upc', db.Unicode)
    format = db.Column('format', db.Unicode)

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized access. Please login.', 'danger')
            return redirect(url_for('home'))
    return wrap

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Route for index page
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        # Get form fields
        username = request.form['username']
        password_candidate = request.form['password']

        # Create cursor
        cur = mysql.connection.cursor()

        # Get user by username
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if result > 0:
            # Get stored password hash
            data = cur.fetchone()
            password = data['password']

            # Compare passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                session['logged_in'] = True
                session['username'] = username

                flash('You are now logged in', 'success')
                return redirect('/view_all/1')
            else:
                error = 'Invalid Login'
                return render_template('index.html', error=error)
            # Close DB connection
            cur.close()
        else:
            error = 'Username not found'
            return render_template('index.html', error=error)

    return render_template('index.html')

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('home'))

# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method == 'POST' and form.validate():
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute Query
        cur.execute("INSERT INTO users(username, password) VALUES(%s, %s)", (username, password))

        # Commit to DB
        mysql.connection.commit()

        # Close DB connection
        cur.close()

        flash('You are now registered and can log in!', 'success')

        return redirect(url_for('home'))

    return render_template('register.html', form=form)

# View all albums. Uses SQLAlchemy for pagination
@app.route('/view_all/<int:page_num>')
def albums(page_num):
   albums = Albums.query.order_by(Albums.title.asc()).paginate(per_page=10, page=page_num, error_out=True)

   return render_template('view_all.html', albums=albums)

# View one album
@app.route('/view_album/<string:catno>/')
def view_album(catno):
    cur = mysql.connection.cursor()
    # Get the album from the 'albums' table
    result = cur.execute("SELECT * FROM albums WHERE catno = %s", [catno])

    album = cur.fetchone()
    # Get list of songs on the album from 'songs' table
    result_two = cur.execute("SELECT * FROM songs WHERE catno = %s ORDER BY "
    + "trackno ASC", [catno])

    songs = cur.fetchall()

    cur.close()

    return render_template('view_album.html', album=album, songs=songs)

# Route for page that has a form to insert a new record into the database
@app.route('/add_album', methods=['GET', 'POST'])
@is_logged_in
def add_album():
    form = AlbumForm()
    if request.method == 'POST' and form.validate():
        catno = form.catno.data.upper()
        artist = form.artist.data
        title = form.title.data
        year = form.year.data
        rlabel = form.rlabel.data
        genre = form.genre.data
        upc = form.upc.data
        format = form.format.data

        # Create Cursor
        cur = mysql.connection.cursor()

        # Execute cursor
        cur.execute("INSERT INTO albums(catno, artist, title, year, rlabel, "
        + "genre, format) VALUES(%s, %s, %s, %s, %s, %s, %s)",
        (catno, artist, title, year, rlabel, genre, format))

        # Commit to DB
        mysql.connection.commit()

        # Close DB connection
        cur.close()

        flash('Album added!', 'success')

        return redirect(url_for('view_album', catno=catno))

    return render_template('add_album.html', form=form)

# Upload album cover art from edit page
@app.route('/upload_cover/<string:catno>', methods=['GET', 'POST'])
@is_logged_in
def upload_cover(catno):
    if request.method == 'POST' and 'photo' in request.files:
        # Get file from user
        file = request.files['photo']
        if allowed_file(file.filename):
            # Get the extention type from file
            ext = os.path.splitext(file.filename)[1]
            # Rename the file with the catalog number and file extension
            file.filename = catno.replace(" ", "") + ext
            # Save cover art
            photos.save(file)
            # Create Cursor
            cur = mysql.connection.cursor()
            # Execute cursor
            cur.execute("UPDATE albums SET albumArt=%s WHERE catno=%s",
            (file.filename, catno))
            # Commit to DB
            mysql.connection.commit()
            # Close DB connection
            cur.close()

            return redirect(url_for('view_album', catno=catno))
        else:
            flash('Incorrect file format! Please select an image file! (PNG, JPG, or JPEG)', 'danger')

            return redirect(url_for('edit_album', catno=catno))
    else:
        flash('Cover art upload error! No file selected!', 'danger')

        return redirect(url_for('edit_album', catno=catno))


    return render_template('view_album.html')

@app.route('/delete_cover/<string:catno>', methods=['GET', 'POST'])
def delete_cover(catno):
    cur = mysql.connection.cursor()

    result = cur.execute("SELECT * FROM albums WHERE catno = %s", [catno])

    album = cur.fetchone()
    cover_art = album['albumArt']
    value = None

    os.remove((os.path.join('static/album_art', cover_art)))
    cur.execute("UPDATE albums SET albumArt=%s WHERE catno=%s", [None, catno])

    mysql.connection.commit()
    cur.close()

    flash('Cover art removed!', 'success')

    return redirect(url_for('edit_album', catno=catno))

# Edit album details
@app.route('/edit_album/<string:catno>/', methods=['GET', 'POST'])
@is_logged_in
def edit_album(catno):
    # Create Cursor
    cur = mysql.connection.cursor()

    # Get album from 'albums' table
    result = cur.execute("SELECT * FROM albums WHERE catno = %s", [catno])

    album = cur.fetchone()

    # Get list of songs on the album from 'songs' table
    result_two = cur.execute("SELECT * FROM songs WHERE catno = %s ORDER BY "
    + "trackno ASC", [catno])

    songs = cur.fetchall()

    # Get form
    form = AlbumForm(request.form)

    # Populate album form fields
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
        cur.execute("UPDATE albums SET artist=%s, title=%s, year=%s, rlabel=%s,"
        + " genre=%s, format=%s WHERE catno=%s",
        (artist, title, year, rlabel, genre, format, catno))
        # Commit to DB
        mysql.connection.commit()
        # Close DB connection
        cur.close()

        flash('Album Updated', 'success')

        return redirect(url_for('view_album', catno=catno))

    return render_template('edit_album.html', album=album, songs=songs, form=form)

@app.route('/add_tracks/<string:catno>', methods=['GET', 'POST'])
@is_logged_in
def add_tracks(catno):

    # Create cursor
    cur = mysql.connection.cursor()
    # Get tracks for display as you're adding them
    result = cur.execute("SELECT * FROM songs WHERE catno=%s ORDER BY trackno "
    + "ASC", [catno])

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

        cur.execute("INSERT INTO songs(catno, trackno, title, duration) "
        + "VALUES(%s, %s, %s, %s)", (catno, trackno, title, duration))

        mysql.connection.commit()

        cur.close()

        flash('Track Added!', 'success')

        return redirect(url_for('add_tracks', catno=catno))

    return render_template('add_tracks.html', songs=songs, form=form)

@app.route('/edit_track/<int:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_track(id):
    cur = mysql.connection.cursor()

    result = cur.execute("SELECT * FROM songs WHERE id=%s", [id])

    song = cur.fetchone()

    catno = song['catno']

    result_two = cur.execute("SELECT * FROM albums WHERE catno=%s", [catno])

    album = cur.fetchone()

    cur.close()

    form = SongForm(request.form)

    # Populate album form fields
    form.trackno.data = song['trackno']
    form.song_title.data = song['title']
    duration_one = song['duration']
    # Split duration string to get minutes
    min_split = duration_one.split(':')[0]
    form.minutes.data = min_split
    # Split duration string to get seconds
    sec_split = duration_one.rsplit(':')[1]
    form.seconds.data = sec_split

    if request.method == 'POST' and form.validate():
        trackno = request.form['trackno']
        title = request.form['song_title']
        minutes = request.form['minutes']
        seconds = request.form['seconds']

        # Add colon between minutes and seconds to insert duration into DB
        duration = minutes + ":" + seconds

        # Create Cursor
        cur = mysql.connection.cursor()
        # Execute cursor
        cur.execute("UPDATE songs SET trackno=%s, title=%s, duration=%s WHERE "
        + "id=%s", (trackno, title, duration, id))
        # Commit to DB
        mysql.connection.commit()
        # Close DB connection
        cur.close()

        flash('Track Details Updated!', 'success')

        return redirect(url_for('edit_track', id=id))

    return render_template('edit_track.html', id=id, album=album, song=song, form=form)

@app.route('/delete_track/<int:id>', methods=['POST'])
@is_logged_in
def delete_track(id):
    #Create cursor
    cur = mysql.connection.cursor()

    result = cur.execute("SELECT catno FROM songs WHERE id=%s", [id])
    song = cur.fetchone()
    catno = song['catno']
    # Execute
    cur.execute("DELETE FROM songs WHERE id = %s", [id])

    # Commit to DB
    mysql.connection.commit()

    #Close DB connection
    cur.close()

    flash('Track removed!', 'success')

    return redirect(url_for('edit_album', catno=catno))

if __name__ == '__main__':
    app.run(debug=True)
