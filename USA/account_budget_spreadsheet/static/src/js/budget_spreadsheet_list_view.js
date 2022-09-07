odoo.define("documents_spreadsheet.BudgetListView", function (require) {
    "use strict";

    const DocumentsListView = require('documents_spreadsheet.ListView');
    const viewRegistry = require("web.view_registry");
    const DocumentsListController = require("documents.DocumentsListController");
    const BudgetController = DocumentsListController.extend({
        _onButtonClicked(ev) {
            const {attrs, record} = ev.data;
            if (attrs.name === "open_budget") {
                ev.data.attrs.type = 'action' 
            }
            this._super(...arguments);
            if (attrs.name === "open_budget") {
                this._openSpreadsheet(record);
            }
        },
        /**
         * Open a document
         *
         * @param {record}
         */
        _openSpreadsheet(record) {
            this.do_action({
                type: "ir.actions.client",
                tag: "action_open_spreadsheet",
                params: {
                    active_id: record.data.id,
                },
            });

        },
    });

    const BudgetListView = DocumentsListView.extend({
        config: Object.assign({}, DocumentsListView.prototype.config, {
            Controller: BudgetController,
        }),
    });

    viewRegistry.add("budget_spreadsheet_list", BudgetListView);
    return BudgetListView;
});