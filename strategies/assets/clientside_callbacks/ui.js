window.dash_clientside = Object.assign({}, window.dash_clientside, {
    ui: {
        showIndStrategy: function(selected_indicators) {
            // Show columns if any indicators are selected
            const shouldShow = selected_indicators && selected_indicators.length > 0;
            return [
                {"display": shouldShow ? "block" : "none"}   // column_3 style
            ];
        },
        preventShow: function(ready, children){
            // Show only if ready AND has children
            const hasChildren = children && children.length > 0;
            return {display: (ready && hasChildren) ? "block" : "none"};
        },
        popoverOpenCloseLabel: function(input_clicks, option_clicks, store_data, input_id, current_label) {
            // безопасные алиасы
            var dc = window.dash_clientside || {};
            var no_update = dc.no_update || {'__dash_clientside_no_update': true};

            var opened = no_update;
            var label = no_update;

            // defensive: если нет input_id - ничего не делаем
            if (!input_id) {
                return [opened, label];
            }

            // try to get triggered id from client ctx
            var ctx = (dc && dc.callback_context) ? dc.callback_context : (window.dash_clientside_callback_context || null);
            var triggered = null;
            if (ctx && ctx.triggered && ctx.triggered.length > 0) {
                triggered = ctx.triggered[0];
            }

            if (triggered && triggered.prop_id) {
                var prop = triggered.prop_id.split('.')[0];
                var trig_id = null;
                try {
                    trig_id = JSON.parse(prop);
                } catch (e) {
                    trig_id = null;
                }

                if (trig_id) {
                    // клик по эл-ту input (тот, у которого role == 'input')
                    if (trig_id.role && trig_id.role === 'input') {
                        if ((input_clicks || 0) > 0) {
                            opened = true;
                        }
                    }
                    // клик по option-btn
                    else if (trig_id.type && trig_id.type === 'option-btn') {
                        // сравниваем скоуп: strategy/condition/index
                        if (String(trig_id.strategy) === String(input_id.strategy) &&
                            trig_id.condition === input_id.condition &&
                            String(trig_id.index) === String(input_id.index)) {
                            opened = false;
                            label = trig_id.label || current_label;
                        }
                    }
                }
            }

            // Если в store есть фиксированная подпись — приоритет
            try {
                var key = String(input_id.strategy) + '_' + input_id.condition + '_' + input_id.index;
                var t = input_id.type;
                if (t === 'column_dropdown' && store_data && store_data[key] && store_data[key].column_label) {
                    label = store_data[key].column_label;
                } else if (t === 'comparison_operator' && store_data && store_data[key] && store_data[key].comparison_operator_label) {
                    label = store_data[key].comparison_operator_label;
                } else if (t === 'column_or_custom_dropdown' && store_data && store_data[key] && store_data[key].column_or_custom_label) {
                    label = store_data[key].column_or_custom_label;
                }
            } catch (e) {
                // ignore
            }

            return [opened, label];
        }
    }
});