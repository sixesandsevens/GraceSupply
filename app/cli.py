import click
from app import db


def register_cli(app):
    @app.cli.command("create-user")
    @click.argument("username")
    @click.password_option()
    def create_user(username, password):
        """Create a new GraceSupply user. Usage: flask create-user <username>"""
        from app.models import User

        if User.query.filter_by(username=username).first():
            click.echo(f"User '{username}' already exists.")
            return

        user = User(username=username, active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created user '{username}'.")
