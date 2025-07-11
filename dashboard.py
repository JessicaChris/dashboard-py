# -*- coding: utf-8 -*-
"""
Created on Mon Jul  7 14:53:36 2025

@modified_by: Jessica
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime

# Utility functions
def style_negative(v, props=''):
    try:
        return props if v < 0 else None
    except:
        pass

def style_positive(v, props=''):
    try:
        return props if v > 0 else None
    except:
        pass

def audience_simple(country):
    if country == 'US':
        return 'USA'
    elif country == 'IN':
        return 'India'
    else:
        return 'Other'

@st.cache_data
def load_data():
    df_agg = pd.read_csv('Aggregated_Metrics_By_Video.csv')  # ✅ No iloc
    df_agg.columns = ['Video','Video title','Video publish time','Comments added','Shares','Dislikes','Likes',
                      'Subscribers lost','Subscribers gained','RPM(USD)','CPM(USD)','Average % viewed','Average view duration',
                      'Views','Watch time (hours)','Subscribers','Your estimated revenue (USD)','Impressions','Impressions ctr(%)']

    df_agg['Video publish time'] = pd.to_datetime(df_agg['Video publish time'], errors='coerce')

    def convert_duration(x):
        try:
            return datetime.strptime(x, '%H:%M:%S')
        except:
            return pd.NaT

    df_agg['Average view duration'] = df_agg['Average view duration'].apply(convert_duration)
    df_agg['Avg_duration_sec'] = df_agg['Average view duration'].apply(lambda x: x.second + x.minute*60 + x.hour*3600 if pd.notnull(x) else np.nan)
    df_agg['Engagement_ratio'] =  (df_agg['Comments added'] + df_agg['Shares'] + df_agg['Dislikes'] + df_agg['Likes']) / df_agg['Views']
    df_agg['Views / sub gained'] = df_agg['Views'] / df_agg['Subscribers gained']
    df_agg.sort_values('Video publish time', ascending = False, inplace = True)

    df_agg_sub = pd.read_csv('Aggregated_Metrics_By_Country_And_Subscriber_Status.csv')
    df_comments = pd.read_csv('Aggregated_Metrics_By_Video.csv')
    df_time = pd.read_csv('Video_Performance_Over_Time.csv')
    df_time['Date'] = pd.to_datetime(df_time['Date'], errors='coerce')

    return df_agg, df_agg_sub, df_comments, df_time

# Load data
df_agg, df_agg_sub, df_comments, df_time = load_data()

# Feature engineering
df_agg_diff = df_agg.copy()
metric_date_12mo = df_agg_diff['Video publish time'].max() - pd.DateOffset(months=12)
median_agg = df_agg_diff[df_agg_diff['Video publish time'] >= metric_date_12mo].median(numeric_only=True)
numeric_cols = df_agg_diff.select_dtypes(include=[np.number]).columns
df_agg_diff[numeric_cols] = (df_agg_diff[numeric_cols] - median_agg).div(median_agg)

# Time delta logic
df_time_diff = pd.merge(df_time, df_agg[['Video', 'Video publish time']], left_on='External Video ID', right_on='Video')
df_time_diff['days_published'] = (df_time_diff['Date'] - df_time_diff['Video publish time']).dt.days

date_12mo = df_agg['Video publish time'].max() - pd.DateOffset(months=12)
df_time_diff_yr = df_time_diff[df_time_diff['Video publish time'] >= date_12mo]

# Views over first 30 days
views_days = pd.pivot_table(df_time_diff_yr, index='days_published', values='Views', aggfunc=[np.mean, np.median, lambda x: np.percentile(x, 80), lambda x: np.percentile(x, 20)]).reset_index()
views_days.columns = ['days_published','mean_views','median_views','80pct_views','20pct_views']
views_days = views_days[views_days['days_published'].between(0,30)]
views_cumulative = views_days[['days_published','median_views','80pct_views','20pct_views']].cumsum()

# Streamlit UI
add_sidebar = st.sidebar.selectbox('Choose View', ['Aggregate Metrics', 'Individual Video Analysis'])

if add_sidebar == 'Aggregate Metrics':
    st.title("Ken Jee YouTube Analytics (Modified by Jess)")

    df_agg_metrics = df_agg[['Video publish time','Views','Likes','Subscribers','Shares','Comments added','RPM(USD)',
                             'Average % viewed','Avg_duration_sec', 'Engagement_ratio','Views / sub gained']]

    metric_date_6mo = df_agg_metrics['Video publish time'].max() - pd.DateOffset(months=6)
    metric_medians6mo = df_agg_metrics[df_agg_metrics['Video publish time'] >= metric_date_6mo].median(numeric_only=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    columns = [col1, col2, col3, col4, col5]

    count = 0
    for i in metric_medians6mo.index:
        with columns[count]:
            delta = (metric_medians6mo[i] - median_agg[i]) / median_agg[i]
            st.metric(label=i, value=round(metric_medians6mo[i],1), delta="{:.2%}".format(delta))
            count = (count + 1) % 5

    # Show Data Table
    df_agg_diff['Publish_date'] = df_agg_diff['Video publish time'].dt.date
    df_display = df_agg_diff[['Video title','Publish_date','Views','Likes','Subscribers','Shares','Comments added',
                              'RPM(USD)','Average % viewed','Avg_duration_sec','Engagement_ratio','Views / sub gained']]

    df_agg_numeric_lst = df_display.select_dtypes(include=[np.number]).columns.tolist()
    df_to_pct = {col: '{:.1%}'.format for col in df_agg_numeric_lst}

    st.dataframe(
        df_display.style
        .applymap(style_negative, props='color:red;')
        .applymap(style_positive, props='color:green;')
        .format(df_to_pct)
    )

elif add_sidebar == 'Individual Video Analysis':
    st.title("🎥 Individual Video Deep Dive")

    videos = df_agg['Video title'].unique()
    video_select = st.selectbox('Pick a video:', videos)

    agg_filtered = df_agg[df_agg['Video title'] == video_select]
    agg_sub_filtered = df_agg_sub[df_agg_sub['Video Title'] == video_select]
    agg_sub_filtered['Country'] = agg_sub_filtered['Country Code'].apply(audience_simple)
    agg_sub_filtered.sort_values('Is Subscribed', inplace=True)

    st.subheader("Audience Breakdown")
    fig = px.bar(agg_sub_filtered, x='Views', y='Is Subscribed', color='Country', orientation='h')
    st.plotly_chart(fig)

    st.subheader("Views in First 30 Days")
    agg_time_filtered = df_time_diff[df_time_diff['Video Title'] == video_select]
    first_30 = agg_time_filtered[agg_time_filtered['days_published'].between(0, 30)].sort_values('days_published')

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['20pct_views'],
                              mode='lines', name='20th percentile', line=dict(color='purple', dash='dash')))
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['median_views'],
                              mode='lines', name='50th percentile', line=dict(color='black', dash='dash')))
    fig2.add_trace(go.Scatter(x=views_cumulative['days_published'], y=views_cumulative['80pct_views'],
                              mode='lines', name='80th percentile', line=dict(color='royalblue', dash='dash')))
    fig2.add_trace(go.Scatter(x=first_30['days_published'], y=first_30['Views'].cumsum(),
                              mode='lines', name='This Video', line=dict(color='firebrick', width=4)))

    fig2.update_layout(title='View Comparison - First 30 Days',
                       xaxis_title='Days Since Published',
                       yaxis_title='Cumulative Views')

    st.plotly_chart(fig2)
