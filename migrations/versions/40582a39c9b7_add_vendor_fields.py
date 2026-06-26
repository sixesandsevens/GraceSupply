"""Initial schema

Revision ID: 40582a39c9b7
Revises:
Create Date: 2026-06-25 21:57:48.143072

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '40582a39c9b7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('category', sa.String(length=80), nullable=False),
        sa.Column('unit', sa.String(length=40), nullable=False),
        sa.Column('current_quantity', sa.Integer(), nullable=False),
        sa.Column('minimum_quantity', sa.Integer(), nullable=False),
        sa.Column('target_quantity', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=120), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('image_filename', sa.String(length=255), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('vendor', sa.String(length=120), nullable=True),
        sa.Column('sku', sa.String(length=120), nullable=True),
        sa.Column('vendor_url', sa.String(length=500), nullable=True),
        sa.Column('estimated_unit_cost', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'inventory_transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('change_amount', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=40), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=80), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['item.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'inventory_count',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('counted_quantity', sa.Integer(), nullable=False),
        sa.Column('counted_at', sa.DateTime(), nullable=False),
        sa.Column('counted_by', sa.String(length=80), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['item.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('inventory_count')
    op.drop_table('inventory_transaction')
    op.drop_table('item')
