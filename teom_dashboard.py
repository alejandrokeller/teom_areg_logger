import dash
from dash import dcc, html, ctx
from dash.dependencies import Input, Output, State
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import configparser

# === Load Configuration ===
config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')

LOG_DIR = Path(config['DASHBOARD']['log_dir'])
DEFAULT_LOG_FILE = LOG_DIR / f"teom_log_{datetime.now().strftime('%Y-%m-%d')}.csv"
UNFILTERED_STEPS = int(config['DASHBOARD']['unfiltered_steps'])

YELLOW_THRESHOLD = float(config['LAMP_THRESHOLDS']['yellow_threshold'])
RED_THRESHOLD_FLOW_3 = float(config['LAMP_THRESHOLDS']['red_threshold_flow_3'])
RED_THRESHOLD_FLOW_LOW = float(config['LAMP_THRESHOLDS']['red_threshold_flow_low'])

app = dash.Dash(__name__)
app.title = 'TEOM Logger Dashboard'

def load_data(unfiltered_steps=None):
    all_files = sorted(LOG_DIR.glob('teom_log_*.csv'))
    df_list = []
    for f in all_files:
        try:
            df = pd.read_csv(f, encoding='latin1')
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            df_list.append(df)
        except Exception as e:
            print(f"[WARN] Could not read {f}: {e}")
    if df_list:
        df = pd.concat(df_list)
        df = df.dropna(subset=['Timestamp']).sort_values('Timestamp')
        # Calculate custome mass concentration
        if {'Frequency (hz)', 'K0 Constant (g/s²)', 'Main Flow (lpm)'}.issubset(df.columns):
            df = df.copy()
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])

            # Convert to numeric and handle missing/invalid values
            freq = pd.to_numeric(df['Frequency (hz)'], errors='coerce')
            k0 = pd.to_numeric(df['K0 Constant (g/s²)'], errors='coerce')
            flow = pd.to_numeric(df['Main Flow (lpm)'], errors='coerce')

            # f1 = current frequency, f0 = frequency 6 samples ago
            f1 = freq
#            f0 = freq.shift(UNFILTERED_STEPS)
            f0 = freq.shift(unfiltered_steps if unfiltered_steps else UNFILTERED_STEPS)
            
            # Δt between current and 6-previous timestamp
#            delta_t = df['Timestamp'].sub(df['Timestamp'].shift(UNFILTERED_STEPS)).dt.total_seconds() / 60.0
            delta_t = df['Timestamp'].sub(df['Timestamp'].shift(unfiltered_steps if unfiltered_steps else UNFILTERED_STEPS)).dt.total_seconds() / 60.0


            # Avoid division by zero and NaNs
            with pd.option_context('mode.use_inf_as_na', True):
                derived = k0 * (1 / f1**2 - 1 / f0**2) * 1000 * 1000000 / flow / delta_t

            # Replace bad values
            df['Mass Concentration unfiltered (µg/m³)'] = derived.replace([float('inf'), -float('inf')], pd.NA).fillna(0).round(3)
            # Replace bad values
            df['delta_t (min)'] = delta_t.replace([float('inf'), -float('inf')], pd.NA).fillna(0).round(2)
        return df
    return pd.DataFrame()

app.layout = html.Div([
    html.H1("TEOM Logger Dashboard"),
    dcc.Interval(id='interval-update', interval=10_000, n_intervals=0),
    
    html.Div([
        html.Label("Select Time Range:"),
        dcc.Dropdown(
            id='preset-dropdown',
            options=[
                {'label': 'Last Hour', 'value': 'last_hour'},
                {'label': 'Last 6 Hours', 'value': 'last_6_hours'},
                {'label': 'Last 12 Hours', 'value': 'last_12_hours'},
                {'label': 'Today', 'value': 'today'},
                {'label': 'This Month', 'value': 'this_month'},
                {'label': 'Custom Range', 'value': 'custom'},
            ],
            value='last_hour',
            clearable=False
        ),
        
        dcc.DatePickerRange(
            id='date-range-picker',
            start_date=datetime.now().date(),
            end_date=datetime.now().date(),
            min_date_allowed=None,
            max_date_allowed=None,
            initial_visible_month=datetime.now().date(),
            display_format='YYYY-MM-DD',
            minimum_nights=0,
            style={'marginTop': '10px'}
        )
        
    ], style={'marginBottom': '20px'}),

    html.Div([
        html.Label("Select Parameter(s):"),
        dcc.Dropdown(
            id='parameter-dropdown',
            value=[],
            placeholder="Select parameter(s)",
            multi=True
        ),
        dcc.Checklist(
            id='multi-axis-toggle',
            options=[{'label': 'Use separate Y-axes', 'value': 'multi'}],
            value=[],
            style={'marginTop': '10px'}
        ),
        html.Label("Resampling Interval:"),
        dcc.Dropdown(
            id='resample-dropdown',
            options=[
                {'label': 'Raw Data', 'value': False},
                {'label': '1-Minute Average', 'value': '1min'},
                {'label': '10-Minute Average', 'value': '10min'},
                {'label': 'Hourly Average', 'value': '1H'}
            ],
            value=False,
            clearable=False,
            style={'marginTop': '5px'}
        )
    ], style={'marginBottom': '20px'}),
    
    dcc.Store(id='selected-parameters-store'),
    dcc.Store(id='available-dates-store'),
    
    html.Div([
        html.Div(id='main-flow-display', style={'fontSize': '18px', 'marginBottom': '5px'}),

        html.Div([
            html.Div(id='filter-loading-display', style={'fontSize': '18px', 'marginRight': '10px'}),
            html.Div(id='filter-indicator-lamp', style={
                'width': '25px',
                'height': '25px',
                'borderRadius': '50%',
                'border': '2px solid black',
                'marginRight': '10px'
            }),
            html.Div(id='filter-warning-text', style={'fontSize': '16px', 'color': 'red'})
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '10px'})
    ], style={'marginBottom': '30px'}),

    
    dcc.Graph(id='parameter-graph'),
    
    html.Div([
        html.Label("Unfiltered Mass Steps:"),
        dcc.Slider(
            id='unfiltered-steps-slider',
            min=1,
            max=120,
            step=1,
            value=UNFILTERED_STEPS,  # default from config
            marks={i: str(i) for i in range(0, 121, 10)},
            tooltip={"placement": "bottom", "always_visible": False}
        )
    ], id='unfiltered-slider-container', style={'display': 'none', 'marginTop': '20px'}),
    
    html.Button("Download CSV", id="download-button", n_clicks=0),
    dcc.Download(id="download-data")

])

@app.callback(
    Output('unfiltered-slider-container', 'style'),
    Input('parameter-dropdown', 'value')
)
def toggle_unfiltered_slider(selected_params):
    if selected_params and "Mass Concentration unfiltered (µg/m³)" in selected_params:
        return {'display': 'block', 'marginTop': '20px'}
    return {'display': 'none'}

@app.callback(
    Output('parameter-dropdown', 'options'),
    Output('parameter-dropdown', 'value'),
    Input('interval-update', 'n_intervals'),
    State('selected-parameters-store', 'data')
)
def update_dropdown(n, stored_selection):
    df = load_data()
    if df.empty:
        return [], []

    options = [{'label': col, 'value': col} for col in df.columns if col != 'Timestamp']
    available = [opt['value'] for opt in options]

    if stored_selection is None and available:
        preserved = [available[0]]
    else:
        preserved = [v for v in stored_selection if v in available] if stored_selection else []
    return options, preserved

@app.callback(
    Output('selected-parameters-store', 'data'),
    Input('parameter-dropdown', 'value')
)
def store_selected_parameters(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

# Callback 1: only update available log dates
@app.callback(
    Output('date-range-picker', 'min_date_allowed'),
    Output('date-range-picker', 'max_date_allowed'),
    Output('available-dates-store', 'data'),
    Input('interval-update', 'n_intervals')
)
def update_available_dates(_):
    all_files = sorted(LOG_DIR.glob('teom_log_*.csv'))
    if not all_files:
        return None, None, []

    dates = [f.stem.replace('teom_log_', '') for f in all_files]
    parsed = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]

    return min(parsed), max(parsed), sorted(set(str(d) for d in parsed))

# Callback 2: update date range only on preset change
@app.callback(
    Output('date-range-picker', 'start_date'),
    Output('date-range-picker', 'end_date'),
    Input('preset-dropdown', 'value'),
    State('date-range-picker', 'start_date'),
    State('date-range-picker', 'end_date')
)
def update_date_range_from_preset(preset, current_start, current_end):
    now = datetime.now()
    if preset == 'last_hour':
        return now - pd.Timedelta(hours=1), now
    elif preset == 'last_6_hours':
        return now - pd.Timedelta(hours=6), now
    elif preset == 'last_12_hours':
        return now - pd.Timedelta(hours=12), now
    elif preset == 'today':
        return now.date(), now
    elif preset == 'this_month':
        return now.replace(day=1).date(), now
    elif preset == 'custom':
        raise dash.exceptions.PreventUpdate
    else:
        return current_start, current_end

@app.callback(
    Output('main-flow-display', 'children'),
    Output('filter-loading-display', 'children'),
    Output('filter-indicator-lamp', 'style'),
    Output('filter-warning-text', 'children'),
    Input('interval-update', 'n_intervals')
)
def update_live_display(n):
    df = load_data()
    if df.empty or 'Main Flow (lpm)' not in df.columns or 'Filter Loading (%)' not in df.columns:
        return "Main Flow: --", "Filter Loading: --", {'backgroundColor': 'grey'}, ""

    latest = df.iloc[-1]
    flow = float(latest['Main Flow (lpm)'])
    loading = float(latest['Filter Loading (%)'])

    # Determine lamp color and warning
    color = 'green'
    warning = ""
    if loading >= RED_THRESHOLD_FLOW_3:
        color = 'red'
        warning = "Replace filter soon!"
    elif loading >= RED_THRESHOLD_FLOW_LOW and flow < 3:
        color = 'red'
        warning = "Replace filter soon!"
    elif loading >= YELLOW_THRESHOLD:
        color = 'yellow'

    lamp_style = {
        'width': '25px',
        'height': '25px',
        'borderRadius': '50%',
        'border': '2px solid black',
        'backgroundColor': color,
        'marginRight': '10px'
    }

    return (
        f"Main Flow: {flow:.2f} lpm",
        f"Filter Loading: {loading:.1f} %",
        lamp_style,
        warning
    )

@app.callback(
    Output('parameter-graph', 'figure'),
    Input('parameter-dropdown', 'value'),
    Input('resample-dropdown', 'value'),
    Input('interval-update', 'n_intervals'),
    Input('date-range-picker', 'start_date'),
    Input('date-range-picker', 'end_date'),
    Input('multi-axis-toggle', 'value'),
    Input('unfiltered-steps-slider', 'value')
)
def update_graph(selected_params, resample_freq, n, start_date, end_date, multi_axis_toggle, unfiltered_steps):
    df = load_data(unfiltered_steps=unfiltered_steps)
    if df.empty or not selected_params:
        return px.line(title="No data available.")

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    if start_dt == end_dt:
        # Extend end time to the end of the selected day
        end_dt += pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    df_filtered = df[(df['Timestamp'] >= start_dt) & (df['Timestamp'] <= end_dt)]

    if resample_freq:
        df_filtered = df_filtered.set_index('Timestamp').resample(resample_freq).mean().reset_index()

    if df_filtered.empty:
        return px.line(title="No data in selected range.")
    
    # Safety check: ensure selected params are actually in the data
    valid_params = [p for p in selected_params if p in df_filtered.columns]
    
    fig = go.Figure()
    use_multi = 'multi' in (multi_axis_toggle or [])
    
    for i, param in enumerate(selected_params):
        axis_name = f'y{i+1}' if use_multi else 'y'
        if param == 'Mass Concentration unfiltered (µg/m³)' and 'delta_t (min)' in df_filtered.columns:
            fig.add_trace(go.Scatter(
                x=df_filtered['Timestamp'],
                y=df_filtered[param],
                mode='lines',
                name=param,
                yaxis=axis_name,
                customdata=df_filtered[['delta_t (min)']].values,
                hovertemplate=(
                    'Time: %{x}<br>'
                    #f'{param}: %{{y}} µg/m³<br>'
                    f'{param}: %{{y}}<br>'
                    'Δt: %{customdata} min<br>'
                    '<extra></extra>'
                )
            ))
        else:
            fig.add_trace(go.Scatter(
                x=df_filtered['Timestamp'],
                y=df_filtered[param],
                mode='lines',
                name=param,
                yaxis=axis_name,
                #hovertemplate=None  # use default
                hovertemplate=(
                    'Time: %{x}<br>'
                    f'{param}: %{{y}}<br>'
                    '<extra></extra>'
                )
            ))

    layout = {
        'title': f"{'Averaged ' if resample_freq else ''}Data from {start_dt:%Y-%m-%d %H:%M} to {end_dt:%Y-%m-%d %H:%M}",
        'xaxis_title': 'Time',
        'legend_title': 'Parameters'
    }

    if use_multi:
        # Primary Y-axis
        layout['yaxis'] = {'title': selected_params[0]}
        # Additional Y-axes
        for i, param in enumerate(selected_params[1:], start=1):
            layout[f'yaxis{i+1}'] = {
                'title': param,
                'overlaying': 'y',
                'side': 'right' if i % 2 == 0 else 'left',
                'position': 1.0 - 0.05 * i  # stagger the axis positions slightly
            }
    else:
        layout['yaxis'] = {'title': 'Value'}

    # Static prevents the layout from reseting (e.g., zoom)
    layout['uirevision'] = "static"  
    fig.update_layout(**layout)
    return fig

@app.callback(
    Output("download-data", "data"),
    Input("download-button", "n_clicks"),
    State("parameter-dropdown", "value"),
    State("resample-dropdown", "value"),
    State("date-range-picker", "start_date"),
    State("date-range-picker", "end_date"),
    State("multi-axis-toggle", "value"),
    State("unfiltered-steps-slider", "value"),
    prevent_initial_call=True
)
def download_filtered_data(n_clicks, selected_params, resample_freq, start_date, end_date, multi_axis_toggle, unfiltered_steps):
    df = load_data(unfiltered_steps=unfiltered_steps)
    if df.empty or not selected_params:
        return dcc.send_data_frame(pd.DataFrame().to_csv, "empty.csv")

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    if start_dt == end_dt:
        end_dt += pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    df_filtered = df[(df['Timestamp'] >= start_dt) & (df['Timestamp'] <= end_dt)]

    if resample_freq:
        df_filtered = df_filtered.set_index('Timestamp').resample(resample_freq).mean().reset_index()

    if df_filtered.empty:
        return dcc.send_data_frame(pd.DataFrame().to_csv, "empty.csv")

    return dcc.send_data_frame(df_filtered[['Timestamp'] + selected_params].to_csv, "teom_filtered_data_export.csv")

if __name__ == '__main__':
    app.run(debug=True)