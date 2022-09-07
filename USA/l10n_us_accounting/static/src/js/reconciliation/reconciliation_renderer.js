odoo.define('l10n_us_accounting.ReconciliationRenderer', function (require) {
    "use strict";

    let LineRenderer = require('account.ReconciliationRenderer').LineRenderer;
    LineRenderer.include({
        events: _.extend({}, LineRenderer.prototype.events, {
            'click table.accounting_view td.sort': '_onSortColumn',
            'click .accounting_view caption .o_exclude_button button': '_onExclude'
        }),

        start: function () {
            let state = this._initialState;
            let model = _.find(state.reconcileModels, function (item) {
                return item.id === state.model_id;
            });
            let $modelName = this.$el.find('div.reconciliation_model_name');
            if (model && state.reconciliation_proposition.length > 0) {
                $modelName.css('display', 'inline-block');
                $modelName.find('span').text(model.name);
            }
            let self = this;

            return this._super.apply(this, arguments).then(function () {
                let numOfLines = self.$el.find('table.accounting_view tbody tr.mv_line').length;
                if (numOfLines === 0) {
                    self._hideReconciliationModelName();
                }
            });
        },

        /**
         * @override
         * Handle when users click on each bank statement line, change partner, update transaction lines...
         * @param {Object} state
         */
        update: function (state) {
            // Remove Bank rule name
            let numOfLines = this.$el.find('table.accounting_view tbody tr.mv_line').length;
            this.filterBatchPayment(state);
            this._super.apply(this, arguments);
            let numOfLinesAfter = this.$el.find('table.accounting_view tbody tr.mv_line').length;
            if (numOfLinesAfter !== numOfLines) {
                this._hideReconciliationModelName();
            }
        },

        /**
         * Odoo calls 'get_batch_payments_data' to get all un-reconciled batch payments and apply them for all BSL.
         * We need to filter them in the suggested list of each based BSL:
         *      Journal must be the same as journal of BSL
         *      Amount of batch payment <= amount of BSL
         *      If st_line.amount_currency < 0, choose OUT batch payment, else IN batch payment.
         * @param {Object} state
         */
         filterBatchPayment: function (state) {
            let relevant_payments = state.relevant_payments;
            let filtered_relevant_payments = [];

            if (relevant_payments.length > 0 && state.st_line) {
                let bsl_amount = state.st_line.amount_currency;
                let journal_id = state.st_line.journal_id;
                relevant_payments.filter(batch => (batch.journal_id === journal_id)).forEach((batch) => {
                    // Bank Reconciliation: Amount Filter and Transaction Type Filter are checked
                    if (batch.bank_review_amount_filter && batch.bank_review_transaction_type_filter){
                        if (bsl_amount < 0 && batch.type === 'outbound' && batch.filter_amount <= -bsl_amount){
                            filtered_relevant_payments.push(batch);
                        }
                        if (bsl_amount >= 0 && batch.type === 'inbound' && batch.filter_amount <= bsl_amount){
                            filtered_relevant_payments.push(batch);
                        }
                    }
                    // Bank Reconciliation: Amount Filter is checked but Transaction Type Filter is not checked
                    if (batch.bank_review_amount_filter && !batch.bank_review_transaction_type_filter){
                        if (bsl_amount < 0 && batch.filter_amount <= -bsl_amount){
                            filtered_relevant_payments.push(batch);
                        }
                        if (bsl_amount >= 0 && batch.filter_amount <= bsl_amount){
                            filtered_relevant_payments.push(batch);
                        }
                    }
                    // Bank Reconciliation: Amount Filter is not checked but Transaction Type Filter is checked
                    if (!batch.bank_review_amount_filter && batch.bank_review_transaction_type_filter){
                        if (bsl_amount < 0 && batch.type === 'outbound'){
                            filtered_relevant_payments.push(batch);
                        }
                        if (bsl_amount >= 0 && batch.type === 'inbound'){
                            filtered_relevant_payments.push(batch);
                        }
                    }

                });
            }
            if (filtered_relevant_payments.length > 0){
                state.relevant_payments = filtered_relevant_payments;
            }
        },

        /**
         * @override
         * Handle if users change fields, such as partner.
         * @param {event} event
         * @private
         */
        _onFieldChanged: function (event) {
            let fieldName = event.target.name;
            if (fieldName === 'partner_id') {
                this._hideReconciliationModelName();
            }
            this._super.apply(this, arguments);
        },

        /**
         * @override
         * Hide reconciliation model name when removing proposition line
         * @param {event} event
         * @private
         */
        _onSelectProposition: function (event) {
            this._hideReconciliationModelName();
            this._super.apply(this, arguments);
        },

        /**
         * @override
         * Hide reconciliation model name when adding line
         * @param {event} event
         * @private
         */
        _onSelectMoveLine: function (event) {
            this._super.apply(this, arguments);
            this._hideReconciliationModelName();
        },

        /**
         * @override
         * Hide reconciliation model name when modifying input amount
         * @param {event} event
         * @private
         */
        _editAmount: function (event) {
            this._super.apply(this, arguments);
            this._hideReconciliationModelName();
        },
        _hideReconciliationModelName: function () {
            this.$el.find('div.reconciliation_model_name').hide();
        },

        /**
         * Sort suggested matching list when users click on header of table.
         * @param {event} event
         * @private
         */
        _onSortColumn: function(event) {
            // Convert string to other values
            let strDateToDate = str => $.datepicker.parseDate('mm/dd/yy', str);
            let strCurrencyToNum = str => Number(str.replace(/[^0-9.-]+/g,""));
            let strNumToNum = str => Number(str.replace(/\u200B/g,''));

            // Get string value from a cell.
            let getCellValue = (row, index) => $(row).children('td').eq(index).text().trim();

            // Get function to sort (ASC)
            let comparer = (index, sort_type) => (a, b) => {
                let valA = getCellValue(a, index);
                let valB = getCellValue(b, index);
                switch (sort_type) {
                    case 'number':
                        return strNumToNum(valA) - strNumToNum(valB);
                    case 'currency':
                        return strCurrencyToNum(valA) - strCurrencyToNum(valB);
                    case 'date':
                        return strDateToDate(valA) - strDateToDate(valB);
                    case 'text':
                        return valA.localeCompare(valB);
                }
            };

            let tables = this.$el.find('table.table_sort');
            // Suggested matching list has been displayed or not.
            let display = window.getComputedStyle(this.$el.find('.o_notebook')[0]).getPropertyValue('display');

            if (tables.length > 0 && display !== 'none') {
                let index = event.target.cellIndex;
                let sort_type = event.target.getAttribute('sort_type');
                let sort_mode = event.target.getAttribute('sort_mode') || 'asc';

                // Remove sort icon and sort mode for all headers
                let cols = this.$el.find('tr.header td.sort');
                _.each(cols, col => {
                    col.setAttribute('sort_mode', '');
                    let icon = $(col).find('span.sort_icon')[0];
                    if (icon) {
                        icon.innerHTML = '';
                    }
                });

                // Update sort icon: up arrow (ASC) or down arrow (DESC)
                let sort_icon = $(event.target).find('span.sort_icon')[0];
                if (sort_icon) {
                    sort_icon.innerHTML = sort_mode === 'desc' ? '&uarr;' : '&darr;';
                }

                // Update sort mode: 'asc' or 'desc'
                event.target.setAttribute('sort_mode', sort_mode === 'desc' ? 'asc' : 'desc');

                _.each(tables, table => {
                    // Get rows after sorting in ASC order.
                    let rows = $(table).find('tr').toArray().sort(comparer(index, sort_type));
                    // Revert rows if sorting in DESC order.
                    rows = sort_mode === 'asc' ? rows.reverse() : rows;
                    _.each(rows, row => $(table).append(row));
                })
            }
        },

        /**
         * Exclude bank statement line.
         * @private
         */
         _onExclude: function () {
            this.trigger_up('exclude');
        },

        /**
         * @override
         * Disable edit partial amount feature -> call onSelect to remove the line
         */
        _onEditAmount: function (event) {
            this._onSelectProposition(event);
        },

    });
}); 
