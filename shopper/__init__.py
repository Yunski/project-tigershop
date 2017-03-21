import logging

from flask import current_app, Flask, request, redirect, url_for, render_template, session
from flask_api import status

from . import model_cloudsql as sql
from . import cas

def create_app(config, debug=False, testing=False, config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(config)

    app.debug = debug
    app.testing = testing

    if config_overrides:
        app.config.update(config_overrides)

    if not app.testing:
        logging.basicConfig(level=logging.INFO)

    with app.app_context():
        model = sql
        model.init_app(app)

    @app.route('/')
    def index():
        if 'netid' in session:
            return redirect(url_for('browse'))
        return render_template('index.html')

    @app.route('/login')
    def login():
        c = cas.CASClient(request.url_root)
        return redirect(c.LoginURL(), code=307)

    @app.route('/login/validate')
    def validate():
        if 'ticket' not in request.args:
            content = 'cas login error'
            return content, status.HTTP_400_BAD_REQUEST
        ticket = request.args.get('ticket')
        c = cas.CASClient(request.url_root)
        netid = c.Validate(ticket)
        if netid is None:
            return redirect('/')
        response = redirect(url_for('browse'), code=status.HTTP_302_FOUND)
        session['netid'] = netid
        user = sql.User.query.filter_by(netid=netid).first()
        if user is None:
            newUser = sql.User(netid=netid, ticket=ticket)
            sql.db.session.add(newUser)
            sql.db.session.commit()
        return response

    @app.route('/logout', methods=['POST'])
    def logout():
        session.pop('netid', None)
        return redirect(url_for('index'))

    @app.route('/browse')
    def browse():
        if 'netid' not in session:
            return redirect(url_for('index'))
        netid = session['netid']
        page = request.args.get('page')
        search = request.args.get('search')
        pageInt = 0
        if page is not None:
            pageInt = int(page)
            start = (pageInt-1) * 12
            end = pageInt * 12
        else:
            pageInt = 1
            start = 0
            end = 12
        length = len(sql.Course.query.all())
        if length < end:
            end = length
        num_pages = length // 12 + (length % 12 > 0)
        results = sql.Course.query[start:end]
        if search is not None:
            baseQuery = sql.Course.query.filter(sql.Course.dept == search)
            length = len(baseQuery.all())
            if length < end:
                end = length
            results = baseQuery.order_by(sql.Course.catalog_number)[start:end]
            num_pages = length // 12 + (length % 12 > 0)
        return render_template('browse.html', netid=netid, courses=results, current=pageInt, num_results=length, pages=num_pages, search=search)

    @app.route('/course')
    def course():
        if 'netid' not in session:
            return redirect(url_for('index'))
        netid = session['netid']
        course_id = request.args.get('id')
        search = request.args.get('search')
        page = request.args.get('page')
        returnURL = "/browse?search={}&page={}".format(search, page)
        course = sql.Course.query.filter_by(c_id=course_id).first()
        reviews = course.reviews
        if course == None:
            # course page not found
            return redirect(url_for('browse'))
        return render_template('course.html', netid=netid, course=course, reviews=reviews, returnURL=returnURL)

    @app.route('/cart')
    def cart():
        if 'netid' not in session:
            return redirect(url_for('index'))
        netid = session['netid']
        return render_template('cart.html', netid=netid)

    @app.route('/rant')
    def rant():
        if 'netid' not in session:
            return redirect(url_for('index'))
        return render_template('rant-space.html')

    # Add an error handler. This is useful for debugging the live application,
    # however, you should disable the output of the exception for production
    # applications.
    @app.errorhandler(500)
    def server_error(e):
        return """
        An internal error occurred: <pre>{}</pre>
        See logs for full stacktrace.
        """.format(e), 500

    return app
