# Generated by Django 3.2.15 on 2023-02-17 03:40
from django.core.management import call_command
from django.db import migrations, models

from usaspending_api.common.helpers.sql_helpers import execute_dml_sql

_index_template_suffix = "index_template"


class Migration(migrations.Migration):
    # call_command(...) issued from RunPython operations does not seem to have insight into the transaction state from
    # prior RunSQL operations. So in order to see tables or DB objects being created or dropped by prior RunSQL steps,
    # the migration steps need to be made non-atomic
    atomic = False

    dependencies = [
        ('search', '0020_auto_20221215_2029'),
    ]

    operations = [
        # STEP 1: Create a placeholder empty table with the same structure as rpt.transaction_search as a place to
        # revise indexes without paying the penalty of doing so on LOTS of data
        migrations.RunSQL(
            sql=f"""
                DROP TABLE IF EXISTS temp.transaction_search_{_index_template_suffix};
                CREATE TABLE temp.transaction_search_{_index_template_suffix} (LIKE rpt.transaction_search);
            """,
            reverse_sql=f"DROP TABLE IF EXISTS temp.transaction_search_{_index_template_suffix};"
        ),
        # STEP 2: Copy all existing rpt.transaction_search indexes and constraints on to the placeholder table
        migrations.RunPython(
            code=lambda apps, _: call_command(
                "copy_table_metadata",
                "--source-table=rpt.transaction_search",
                f"--dest-table=temp.transaction_search_{_index_template_suffix}",
                f"--dest-suffix={_index_template_suffix}",
                "--index-concurrency=15",
            ),
            reverse_code=lambda apps, _: execute_dml_sql(
                f"""
                DROP TABLE IF EXISTS temp.transaction_search_{_index_template_suffix};
                CREATE TABLE temp.transaction_search_{_index_template_suffix} (LIKE rpt.transaction_search);
                """,
                apps.get_model("search", "transactionsearch")
            )
        ),

        # STEP 3: DROP, CREATE, or ALTER indexes on the placeholder table to establish the final set of index
        # templates going forward

        migrations.RunSQL(
            # DROP the pkey. Try dropping as CONSTRAINT first, then as UNIQUE INDEX. There is already a
            # When we make this a partition table, with partition key = is_fpds, UNIQUE indexes now need to include
            # the partition key as well as the unique field
            sql=f"""
                ALTER TABLE temp.transaction_search_{_index_template_suffix} DROP CONSTRAINT IF EXISTS transaction_search_pkey_{_index_template_suffix};
                DROP INDEX IF EXISTS temp.transaction_search_pkey_{_index_template_suffix}; 
                CREATE TABLE IF NOT EXISTS temp.transaction_search_{_index_template_suffix} (LIKE rpt.transaction_search);
                CREATE INDEX IF NOT EXISTS ts_idx_transaction_id_{_index_template_suffix} ON temp.transaction_search_{_index_template_suffix}(transaction_id int8_ops);
                CREATE UNIQUE INDEX ts_idx_is_fpds_transaction_id_{_index_template_suffix} ON temp.transaction_search_{_index_template_suffix}(is_fpds bool_ops,transaction_id int8_ops);
            """,
            reverse_sql=f"""
                DROP INDEX IF EXISTS temp.ts_idx_is_fpds_transaction_id_{_index_template_suffix};
                CREATE TABLE IF NOT EXISTS temp.transaction_search_{_index_template_suffix} (LIKE rpt.transaction_search);
                CREATE UNIQUE INDEX transaction_search_pkey_{_index_template_suffix} ON temp.transaction_search_{_index_template_suffix}(transaction_id int8_ops);
            """,
        ),
        migrations.RunSQL(
            # Make INDEX on is_fpds not simply for pre 2008 data with action_date conditions
            sql=f"""
                    DROP INDEX temp.ts_idx_is_fpds_pre2008_{_index_template_suffix}; 
                    CREATE INDEX ts_idx_is_fpds_{_index_template_suffix} ON temp.transaction_search_{_index_template_suffix}(is_fpds bool_ops);
                """,
            reverse_sql=f"""
                    DROP INDEX IF EXISTS temp.ts_idx_is_fpds_{_index_template_suffix}; 
                    CREATE TABLE IF NOT EXISTS temp.transaction_search_{_index_template_suffix} (LIKE rpt.transaction_search);
                    CREATE INDEX IF NOT EXISTS ts_idx_is_fpds_pre2008_{_index_template_suffix} ON temp.transaction_search_{_index_template_suffix}(is_fpds bool_ops) WHERE action_date < '2007-10-01'::date;
                """,
        ),
        migrations.RunSQL(
            # Create mirrored indexes on the rpt schema table side that are new on the template side
            sql=f"""
                CREATE UNIQUE INDEX ts_idx_is_fpds_transaction_id ON rpt.transaction_search(is_fpds bool_ops,transaction_id int8_ops);
                CREATE INDEX ts_idx_is_fpds ON rpt.transaction_search(is_fpds bool_ops);
                DROP INDEX rpt.ts_idx_is_fpds_pre2008;
            """,
            reverse_sql=f"""
                CREATE INDEX IF NOT EXISTS ts_idx_is_fpds_pre2008 ON rpt.transaction_search(is_fpds bool_ops) WHERE action_date < '2007-10-01'::date;
                DROP INDEX IF EXISTS rpt.ts_idx_is_fpds; 
                DROP INDEX IF EXISTS rpt.ts_idx_is_fpds_transaction_id;
            """,
            state_operations=[
                migrations.RemoveIndex(
                    model_name='transactionsearch',
                    name='ts_idx_is_fpds_pre2008',
                ),
                migrations.AddIndex(
                    model_name='transactionsearch',
                    index=models.Index(fields=['is_fpds'], name='ts_idx_is_fpds'),
                ),
                # While the RunSQL brings the DB state in-line with the declared state of the model (mostly)
                # In this case, the DB state operations are short of the declared model state
                #   - we ARE creating a UNIQUE INDEX that would come with the UniqueConstraint,
                #   - but NOT creating the actual UNIQUE CONSTRAINT itself
                migrations.AddConstraint(
                    model_name='transactionsearch',
                    constraint=models.UniqueConstraint(
                        fields=('is_fpds', 'transaction'),
                        name='ts_idx_is_fpds_transaction_id'
                    ),
                ),
            ]
        ),

        # STEP 4: Create the new (empty for now) partitioned tables in the temp schema. They are placeholders that
        # will get data loaded into them, indexes applied, and then swapped in for the real rpt. schema tables.
        migrations.RunSQL(
            sql=f"""
                DROP TABLE IF EXISTS temp.transaction_search_temp;
                CREATE TABLE temp.transaction_search_temp (LIKE rpt.transaction_search) PARTITION BY LIST(is_fpds);
            """,
            reverse_sql=f"""
                DROP TABLE IF EXISTS temp.transaction_search_temp;
            """,
        ),

        # STEP 5: Create and attach child partitions as tables with key values
        migrations.RunSQL(
            sql=f"""
                CREATE TABLE temp.transaction_search_fabs_temp PARTITION OF temp.transaction_search_temp FOR VALUES IN (FALSE); 
                CREATE TABLE temp.transaction_search_fpds_temp PARTITION OF temp.transaction_search_temp FOR VALUES IN (TRUE); 
            """,
            reverse_sql=f"""
                DROP TABLE IF EXISTS temp.transaction_search_fabs_temp;
                DROP TABLE IF EXISTS temp.transaction_search_fpds_temp;
            """,
        ),
    ]
