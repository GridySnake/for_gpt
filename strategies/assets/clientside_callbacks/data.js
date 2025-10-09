window.dash_clientside = Object.assign({}, window.dash_clientside, {
    data: {
        clearColumn1: function(n_clicks) {
            if (!n_clicks) { return [dash_clientside.no_update,
                                     dash_clientside.no_update,
                                     dash_clientside.no_update,
                                     dash_clientside.no_update]; }
            // 0) dropdown_coin
            var coin = "AAPLXUSDT";
            // 1) date_picker
            var startDate = "2022-01-01";
            var endDate   = new Date().toISOString().split("T")[0];
            // 2) dropdown_interval
            var interval = "720";
            // 3) dropdown_indicators
            var indicators = [];
            return [coin,
                    startDate,
                    endDate,
                    interval,
                    indicators];
        }
    }
});