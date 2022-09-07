// We will define our own convertFormulas function to override PARSE function
// of Odoo OOTB.
// Some functions need to be redefined to use convertFormulas:
// convertPivotsFormulas, _removeInvalidPivotRows, getDataFromTemplate

odoo.define('account_budget_spreadsheet.BudgetSpreadsheetWidget', function (require) {
    "use strict";

    var Widget = require('web.Widget');
    var { useService } = require('@web/core/utils/hooks');
    var widget_registry = require('web.widget_registry');
    const { getDataFromTemplate } = require("documents_spreadsheet.pivot_utils");
    const core = require('web.core');
    var _t = core._t;

    var BudgetSpreadsheetWidget = Widget.extend({
            template: 'account_budget_spreadsheet.budget_spreadsheet_button',
            events: _.extend({}, Widget.prototype.events, {
                '.create_new_spreadsheet': '_createSpreadsheet'
            }),

            init: function (parent, params) {
                this.data = params.data;
                this.fields = params.fields;
                this.notification = useService("notification")
                this._super(parent);
            }
            ,

            start: function () {
                const self = this;
                this.$el.bind('click', function () {
                    const data = self.data;
                    return self._createSpreadsheet(data);
                });
            }
            ,
            updateState: function (state) {
                this.data = state.data;
            }
            ,
            _createSpreadsheet(data) {
                const {name, report_type, period_type, year, analytic_account_id, create_budget_from_last_year} = data;
                if (name === false) {
                    const options = {title:_t("Warning"), message: "Name must be required", type: "danger" };
                    this.notification.notify(options)
                    return;
                }
                let analytic_account = false;
                if (data['analytic_account_id']) {
                    analytic_account = analytic_account_id['data']['id'];
                }

                let self = this;
                this._rpc({
                    model: 'documents.document',
                    method: 'create_spreadsheet_from_report',
                    args: [[], period_type, report_type, name, year, analytic_account, create_budget_from_last_year]
                }).then(async function (data) {
                    let spreadsheetId = data['spreadsheet_id']
                    const processed_data = await getDataFromTemplate(self._rpc.bind(self), spreadsheetId);
                    const spreadsheet_id = await self._rpc({
                        model: "documents.document",
                        method: "create",
                        args: [
                            {
                                name: data['spreadsheet_name'],
                                mimetype: "application/o-spreadsheet",
                                handler: "spreadsheet",
                                raw: JSON.stringify(processed_data),
                                is_budget_spreadsheet: true,
                                folder_id: data['folder_id'],
                                report_type: report_type,
                                period_type: period_type,
                                analytic_account_id: data['analytic_account_id'],
                                year: year
                            },
                        ],
                    });
                    self.do_action({
                        type: "ir.actions.client",
                        tag: "action_open_spreadsheet",
                        params: {
                            active_id: spreadsheet_id,
                        },
                    });
                });
            }
            ,

        })
    ;

    widget_registry.add('budget_spreadsheet_widget', BudgetSpreadsheetWidget);

    return BudgetSpreadsheetWidget;
});