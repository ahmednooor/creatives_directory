### Imports
import os, sys
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import sqlalchemy
# from cs50 import SQL
import schedule
import time

### CS50 wrapper for SQLAlchemy
class SQL(object):
    """Wrap SQLAlchemy to provide a simple SQL API."""

    def __init__(self, url):
        """
        Create instance of sqlalchemy.engine.Engine.

        URL should be a string that indicates database dialect and connection arguments.

        http://docs.sqlalchemy.org/en/latest/core/engines.html#sqlalchemy.create_engine
        """
        try:
            self.engine = sqlalchemy.create_engine(url)
        except Exception as e:
            raise RuntimeError(e)

    def execute(self, text, *multiparams, **params):
        """
        Execute a SQL statement.
        """
        try:

            # bind parameters before statement reaches database, so that bound parameters appear in exceptions
            # http://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.text
            # https://groups.google.com/forum/#!topic/sqlalchemy/FfLwKT1yQlg
            # http://docs.sqlalchemy.org/en/latest/core/connections.html#sqlalchemy.engine.Engine.execute
            # http://docs.sqlalchemy.org/en/latest/faq/sqlexpressions.html#how-do-i-render-sql-expressions-as-strings-possibly-with-bound-parameters-inlined
            statement = sqlalchemy.text(text).bindparams(*multiparams, **params)
            result = self.engine.execute(str(statement.compile(compile_kwargs={"literal_binds": True})))

            # if SELECT (or INSERT with RETURNING), return result set as list of dict objects
            if result.returns_rows:
                rows = result.fetchall()
                return [dict(row) for row in rows]

            # if INSERT, return primary key value for a newly inserted row
            elif result.lastrowid is not None:
                return result.lastrowid

            # if DELETE or UPDATE (or INSERT without RETURNING), return number of rows matched
            else:
                return result.rowcount

        # if constraint violated, return None
        except sqlalchemy.exc.IntegrityError:
            return None

        # else raise error
        except Exception as e:
            raise RuntimeError(e)


### configure root directory path relative to this file
THIS_FOLDER_G = ""
if getattr(sys, 'frozen', False):
    # frozen
    THIS_FOLDER_G = os.path.dirname(sys.executable)
else:
    # unfrozen
    THIS_FOLDER_G = os.path.dirname(os.path.realpath(__file__))

### configure CS50 Library to use SQLite database
db = SQL("sqlite:///" + THIS_FOLDER_G + "/db/system.db")

### configure mail
URL_Tokenizer = URLSafeTimedSerializer('Thisisasecret!')


# CRON JOBS
def clear_expired_email_tokens():
    print('JOB STARTED: Non-Confirmed Accounts Deletion.')
    creatives = db.execute("SELECT * FROM creatives")
    creatives_len = len(creatives)
    for i in range(creatives_len):
        if creatives[i]['email_confirmation_token'] != '':
            try:
                email = URL_Tokenizer.loads(creatives[i]['email_confirmation_token'], salt='email-confirm', max_age=(3600 * 12))
            except SignatureExpired:
                db.execute("DELETE FROM creatives WHERE id=:id AND email_confirmed=:email_confirmed", id=creatives[i]['id'], email_confirmed='false')
                print('JOB PROCESS: Non-Confirmed Account Deleted!', email)
    print('JOB ENDED: Non-Confirmed Accounts Deletion.')

schedule.every(6).hours.do(clear_expired_email_tokens)

print("CRON JOBS RUNNING ...")

while True:
    schedule.run_pending()
    time.sleep(1)
