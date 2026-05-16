import sqlalchemy
import sqlalchemy.orm as orm
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import joinedload, scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, redirect, request, url_for, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, EmailField
from wtforms.validators import DataRequired, EqualTo

SqlAlchemyBase = declarative_base()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fnjkrngvekrngvjerngvjkernf'


# --- МОДЕЛИ ---

class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    email = sqlalchemy.Column(sqlalchemy.String, unique=True, index=True)
    hashed_password = sqlalchemy.Column(sqlalchemy.String)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=True)

    def set_password(self, password):
        self.hashed_password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.hashed_password, password)


class Task(SqlAlchemyBase):
    __tablename__ = 'tasks'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    difficulty = sqlalchemy.Column(sqlalchemy.String, default="Medium")
    title = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    content = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    language = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"))

    user = orm.relationship('User')
    # Связь с решениями (backref позволяет обращаться task.solutions)
    solutions = orm.relationship('Solution', backref='task', cascade="all, delete-orphan")


class Solution(SqlAlchemyBase):
    __tablename__ = 'solutions'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    code = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    task_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("tasks.id"))
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"))

    user = orm.relationship('User')

engine = sqlalchemy.create_engine('sqlite:///mars.db?check_same_thread=False')
db_session = scoped_session(sessionmaker(bind=engine))
SqlAlchemyBase.metadata.create_all(engine)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db_session.get(User, int(user_id))


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


class LoginForm(FlaskForm):
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль',
                                   validators=[DataRequired(), EqualTo('password', message="Пароли не совпадают")])
    name = StringField('Имя', validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')


@app.route('/')
def index():
    tasks = db_session.query(Task).options(joinedload(Task.user)).all()
    return render_template('index.html', tasks=tasks)


@app.route('/task/<int:task_id>')
def task_detail(task_id):
    task = db_session.query(Task).options(
        joinedload(Task.solutions).joinedload(Solution.user)
    ).filter(Task.id == task_id).first()

    if not task:
        abort(404)
    return render_template('task_detail.html', task=task)


@app.route('/task/<int:task_id>/solution', methods=['POST'])
@login_required
def add_solution(task_id):
    code = request.form.get('solution_code')
    if code:
        new_solution = Solution(code=code, task_id=task_id, user_id=current_user.id)
        db_session.add(new_solution)
        db_session.commit()
    return redirect(url_for('task_detail', task_id=task_id))


@app.route('/make_task', methods=['GET', 'POST'])
@login_required
def make_task():
    if request.method == 'POST':
        title = request.form.get("title")
        content = request.form.get("content")
        language = request.form.get("language")
        difficulty = request.form.get("difficulty", "Medium")
        new_task = Task(
            title=title, content=content,
            language=language, difficulty=difficulty,
            user_id=current_user.id
        )
        db_session.add(new_task)
        db_session.commit()
        return redirect('/')
    return render_template('make_task.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if db_session.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', form=form, message="Такой пользователь уже есть")
        user = User(email=form.email.data, name=form.name.data)
        user.set_password(form.password.data)
        db_session.add(user)
        db_session.commit()
        login_user(user)
        return redirect("/")
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db_session.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/")
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")

@app.route('/mytasks')
@login_required
def my_tasks():
    tasks = db_session.query(Task).filter(Task.user_id == current_user.id).all()
    return render_template('index.html', tasks=tasks, title="Мои задачи")


if __name__ == '__main__':
    app.run(port=9999, host='127.0.0.1')
