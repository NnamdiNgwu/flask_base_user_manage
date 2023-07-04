import os
import subprocess

#from flask import Flask
from dotenv import load_dotenv, find_dotenv
from flask.cli import AppGroup, with_appcontext, FlaskGroup, ScriptInfo

from flask_migrate import Migrate, MigrateCommand
from flask_sqlalchemy import SQLAlchemy
from redis import Redis
from rq import Connection, Queue, Worker

from app import create_app, db
from app.models import Role, User
from config import Config


_ = load_dotenv(find_dotenv())
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)

cli = AppGroup('manage', help='Manage commands')


def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role)

@app.cli.command('shell')
@with_appcontext
def shell_command():
    """Start a Python shell with the Flask app context."""
    import code

    context = make_shell_context()
    code.interact(local=context)


@app.cli.command('db')
@with_appcontext
def db_command():
    """Run database migrations."""
    MigrateCommand().run()


@app.cli.command('runserver')
@with_appcontext
def runserver_command():
    """Run the development server."""
    app.run(host='0.0.0.0')


@app.cli.command('test')
@with_appcontext
def test_command():
    """Run the unit tests."""
    import unittest

    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)


@app.cli.command('recreate_db')
@with_appcontext
def recreate_db_command():
    """
    Recreates a local database. You probably should not use this on
    production.
    """
    db.drop_all()
    db.create_all()
    db.session.commit()


@app.cli.command('add_fake_data')
@with_appcontext
def add_fake_data_command():
    """
    Adds fake data to the database.
    """
    User.generate_fake(count=10)


@app.cli.command('setup_dev')
@with_appcontext
def setup_dev_command():
    """Runs the set-up needed for local development."""
    setup_general_command()


@app.cli.command('setup_prod')
@with_appcontext
def setup_prod_command():
    """Runs the set-up needed for production."""
    setup_general_command()


def setup_general_command():
    """Runs the set-up needed for both local development and production.
    Also sets up the first admin user."""
    Role.insert_roles()
    admin_query = Role.query.filter_by(name='Administrator')
    if admin_query.first() is not None:
        if User.query.filter_by(email=Config.ADMIN_EMAIL).first() is None:
            user = User(
                first_name='Admin',
                last_name='Account',
                password=Config.ADMIN_PASSWORD,
                confirmed=True,
                email=Config.ADMIN_EMAIL)
            db.session.add(user)
            db.session.commit()
            print('Added administrator {}'.format(user.full_name()))


@app.cli.command('run_worker')
@with_appcontext
def run_worker_command():
    """Initializes a slim rq task queue."""
    listen = ['default']
    conn = Redis(
        host=app.config['RQ_DEFAULT_HOST'],
        port=app.config['RQ_DEFAULT_PORT'],
        db=0,
        password=app.config['RQ_DEFAULT_PASSWORD'])

    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()


@app.cli.command('format')
@with_appcontext
def format_command():
    """Runs the yapf and isort formatters over the project."""
    isort = 'isort -rc *.py app/'
    yapf = 'yapf -r -i *.py app/'

    print('Running {}'.format(isort))
    subprocess.call(isort, shell=True)

    print('Running {}'.format(yapf))
    subprocess.call(yapf, shell=True)


if __name__ == '__main__':
    #cli = FlaskGroup(app)
    app.cli.add_command(cli)
    app.run()
    #cli()
