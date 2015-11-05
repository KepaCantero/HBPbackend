"""
This script has to be run each time the data model is modified.
The full documentation can be found here: https://flask-migrate.readthedocs.org/en/latest/
If you do not have time to read it, here is a small excerpt:

You can then generate an initial migration:
  python manage.py db migrate
The migration script needs to be reviewed and edited, as Alembic currently does not detect
every change you make to your models. In particular, Alembic is currently unable to detect
indexes. Once finalized, the migration script also needs to be added to version control.

Then you can apply the migration to the database:
   python manage.py db upgrade
Then each time the database models change repeat the migrate and upgrade commands.
To sync the database in another system just refresh the migrations folder from source
control and run the upgrade command.
"""

from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from hbp_nrp_backend.rest_server import app, db, init


if __name__ == '__main__':
    init()
    migrate = Migrate(app, db, compare_type=True)
    manager = Manager(app)
    manager.add_command('db', MigrateCommand)
    manager.run()