"""empty message

Revision ID: 438b972add0f
Revises: None
Create Date: 2015-11-05 09:44:59.531591

"""

# revision identifiers, used by Alembic.
revision = '438b972add0f'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('collab_context',
    sa.Column('context_id', sa.Integer(), nullable=False),
    sa.Column('experiment_configuration', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('context_id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('collab_context')
    ### end Alembic commands ###
