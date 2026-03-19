from backend.plugins.base import BingoPlugin, ConnectorRegistration


class BingoCsvPlugin(BingoPlugin):

    @property
    def name(self) -> str:
        return "bingo-csv-connector"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "CSV/Excel dataset connector — upload files as queryable datasets"

    def connectors(self) -> list[ConnectorRegistration]:
        from bingo_csv_connector.connector import DatasetSQLiteConnector

        def _on_delete(connection):
            if connection.dataset_table_name:
                from bingo_csv_connector.service import delete_dataset_sqlite
                delete_dataset_sqlite(connection.dataset_table_name)

        def _on_test(connection):
            return {"success": True, "message": "Dataset connection — no external host to test"}

        return [ConnectorRegistration(
            type_id="dataset",
            display_name="CSV / Excel",
            description="Upload a CSV or Excel file as a queryable dataset",
            default_port=0,
            badge_variant="secondary",
            connector_class=DatasetSQLiteConnector,
            on_delete=_on_delete,
            on_test=_on_test,
            skip_schema_refresh=True,
            sql_dialect_hint="SQLite (table is always 'data', use strftime() for dates, no ILIKE, no :: casting)",
        )]

    def api_routers(self) -> list[tuple]:
        from bingo_csv_connector.routes import router
        return [(router, "/api/connections")]
