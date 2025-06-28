#!/usr/bin/env python3
"""
Daily Deals Nose - Web Admin Panel
Complete web interface for managing the deal bot
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from supabase import create_client
import os
from datetime import datetime, timedelta
import json
import logging
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('ADMIN_PASSWORD', 'your-secret-key-change-this')

# Supabase setup
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def dashboard():
    """Main dashboard route"""
    if 'authenticated' not in session:
        return redirect(url_for('login_page'))
    
    try:
        # Get analytics data
        deals = supabase.table('deals').select('*').execute()
        subscribers = supabase.table('subscribers').select('*').execute()
        posts = supabase.table('posts').select('*').execute()
        analytics = supabase.table('analytics').select('*').execute()
        
        # Calculate metrics
        total_revenue = sum(float(deal.get('revenue', 0)) for deal in deals.data)
        total_clicks = sum(int(deal.get('clicks', 0)) for deal in deals.data)
        total_conversions = sum(int(deal.get('conversions', 0)) for deal in deals.data)
        
        # Today's metrics
        today = datetime.now().date()
        today_deals = [d for d in deals.data if d.get('posted_at', '').startswith(str(today))]
        today_revenue = sum(float(d.get('revenue', 0)) for d in today_deals)
        today_clicks = sum(int(d.get('clicks', 0)) for d in today_deals)
        
        # Weekly growth
        week_ago = today - timedelta(days=7)
        week_subs = [s for s in subscribers.data 
                    if datetime.fromisoformat(s.get('joined_at', datetime.now().isoformat())).date() >= week_ago]
        
        analytics_data = {
            'total_deals': len(deals.data),
            'total_subscribers': len(subscribers.data),
            'total_posts': len(posts.data),
            'total_revenue': total_revenue,
            'total_clicks': total_clicks,
            'total_conversions': total_conversions,
            'today_deals': len(today_deals),
            'today_revenue': today_revenue,
            'today_clicks': today_clicks,
            'week_new_subs': len(week_subs),
            'conversion_rate': (total_conversions / max(total_clicks, 1)) * 100,
            'avg_revenue_per_deal': total_revenue / max(len(deals.data), 1),
            'avg_revenue_per_click': total_revenue / max(total_clicks, 1)
        }
        
        # Get recent deals for display
        recent_deals = sorted(deals.data, key=lambda x: x.get('posted_at', ''), reverse=True)[:10]
        
        return render_template('dashboard.html', 
                             analytics=analytics_data, 
                             recent_deals=recent_deals)
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return render_template('error.html', error=str(e))

@app.route('/login')
def login_page():
    """Login page"""
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    """Handle login authentication"""
    password = request.form.get('password') or request.json.get('password')
    
    if password == ADMIN_PASSWORD:
        session['authenticated'] = True
        session['login_time'] = datetime.now().isoformat()
        return jsonify({'success': True, 'message': 'Login successful'})
    
    return jsonify({'success': False, 'message': 'Invalid password'}), 401

@app.route('/logout')
def logout():
    """Handle logout"""
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/deals')
@login_required
def api_deals():
    """Get all deals via API"""
    try:
        deals = supabase.table('deals').select('*').order('posted_at', desc=True).execute()
        return jsonify({'success': True, 'data': deals.data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deals', methods=['POST'])
@login_required
def api_create_deal():
    """Create a new deal via API"""
    try:
        deal_data = request.json
        
        # Validate required fields
        required_fields = ['title', 'original_price', 'deal_price', 'affiliate_link']
        for field in required_fields:
            if field not in deal_data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400
        
        # Calculate discount percentage
        original = float(deal_data['original_price'])
        deal = float(deal_data['deal_price'])
        discount = int(((original - deal) / original) * 100)
        deal_data['discount_percentage'] = discount
        
        # Set default values
        deal_data.setdefault('description', '')
        deal_data.setdefault('category', 'General')
        deal_data.setdefault('source', 'Manual')
        deal_data.setdefault('status', 'active')
        deal_data.setdefault('clicks', 0)
        deal_data.setdefault('conversions', 0)
        deal_data.setdefault('revenue', 0)
        
        # Insert into database
        result = supabase.table('deals').insert(deal_data).execute()
        
        return jsonify({'success': True, 'data': result.data[0]})
        
    except Exception as e:
        logger.error(f"Error creating deal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deals/<int:deal_id>', methods=['PUT'])
@login_required
def api_update_deal(deal_id):
    """Update a deal via API"""
    try:
        deal_data = request.json
        
        # Update deal
        result = supabase.table('deals').update(deal_data).eq('id', deal_id).execute()
        
        if not result.data:
            return jsonify({'success': False, 'error': 'Deal not found'}), 404
        
        return jsonify({'success': True, 'data': result.data[0]})
        
    except Exception as e:
        logger.error(f"Error updating deal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deals/<int:deal_id>', methods=['DELETE'])
@login_required
def api_delete_deal(deal_id):
    """Delete a deal via API"""
    try:
        result = supabase.table('deals').delete().eq('id', deal_id).execute()
        return jsonify({'success': True, 'message': 'Deal deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting deal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/subscribers')
@login_required
def api_subscribers():
    """Get subscriber statistics"""
    try:
        subscribers = supabase.table('subscribers').select('*').execute()
        
        # Calculate metrics
        total = len(subscribers.data)
        today = datetime.now().date()
        
        # Group by date for chart
        daily_signups = {}
        for sub in subscribers.data:
            join_date = datetime.fromisoformat(sub.get('joined_at', datetime.now().isoformat())).date()
            daily_signups[str(join_date)] = daily_signups.get(str(join_date), 0) + 1
        
        # Get recent signups
        recent_subs = sorted(subscribers.data, 
                           key=lambda x: x.get('joined_at', ''), 
                           reverse=True)[:20]
        
        return jsonify({
            'success': True,
            'total_subscribers': total,
            'daily_signups': daily_signups,
            'recent_subscribers': recent_subs
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics')
@login_required
def api_analytics():
    """Get comprehensive analytics"""
    try:
        # Get all data
        deals = supabase.table('deals').select('*').execute()
        posts = supabase.table('posts').select('*').execute()
        subscribers = supabase.table('subscribers').select('*').execute()
        analytics = supabase.table('analytics').select('*').execute()
        
        # Calculate comprehensive metrics
        total_revenue = sum(float(deal.get('revenue', 0)) for deal in deals.data)
        total_clicks = sum(int(deal.get('clicks', 0)) for deal in deals.data)
        
        # Revenue by category
        category_revenue = {}
        category_deals = {}
        for deal in deals.data:
            category = deal.get('category', 'Unknown')
            revenue = float(deal.get('revenue', 0))
            category_revenue[category] = category_revenue.get(category, 0) + revenue
            category_deals[category] = category_deals.get(category, 0) + 1
        
        # Revenue over time (last 30 days)
        revenue_timeline = {}
        for deal in deals.data:
            posted_date = deal.get('posted_at', '')[:10]  # Get date part
            revenue = float(deal.get('revenue', 0))
            revenue_timeline[posted_date] = revenue_timeline.get(posted_date, 0) + revenue
        
        # Top performing deals
        top_deals = sorted(deals.data, 
                          key=lambda x: float(x.get('revenue', 0)), 
                          reverse=True)[:10]
        
        return jsonify({
            'success': True,
            'total_revenue': total_revenue,
            'total_clicks': total_clicks,
            'total_deals': len(deals.data),
            'total_subscribers': len(subscribers.data),
            'category_revenue': category_revenue,
            'category_deals': category_deals,
            'revenue_timeline': revenue_timeline,
            'top_deals': top_deals
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings')
@login_required
def api_get_settings():
    """Get bot settings"""
    try:
        settings = supabase.table('settings').select('*').execute()
        settings_dict = {s['key']: s['value'] for s in settings.data}
        return jsonify({'success': True, 'settings': settings_dict})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
@login_required
def api_update_settings():
    """Update bot settings"""
    try:
        new_settings = request.json
        
        for key, value in new_settings.items():
            supabase.table('settings').upsert({
                'key': key,
                'value': str(value),
                'updated_at': datetime.now().isoformat()
            }, on_conflict='key').execute()
        
        return jsonify({'success': True, 'message': 'Settings updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/deals')
@login_required
def deals_page():
    """Deals management page"""
    return render_template('deals.html')

@app.route('/subscribers')
@login_required
def subscribers_page():
    """Subscribers management page"""
    return render_template('subscribers.html')

@app.route('/analytics')
@login_required
def analytics_page():
    """Analytics page"""
    return render_template('analytics.html')

@app.route('/settings')
@login_required
def settings_page():
    """Settings page"""
    return render_template('settings.html')

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error='Page not found'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error='Internal server error'), 500

if __name__ == '__main__':
    # Validate environment variables
    if not all([SUPABASE_URL, SUPABASE_KEY]):
        logger.error("Missing required environment variables: SUPABASE_URL, SUPABASE_SERVICE_KEY")
        exit(1)
    
    logger.info("🌐 Starting Daily Deals Nose Web Admin Panel...")
    logger.info(f"🔑 Admin password: {ADMIN_PASSWORD}")
    
    # Run the web application
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    app.run(debug=debug, host='0.0.0.0', port=port)
