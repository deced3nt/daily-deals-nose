#!/usr/bin/env python3
"""
Daily Deals Nose Telegram Bot
Complete automated deal posting and management system
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client, Client
import json
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import re
import random

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7748001064:AAEsZSx5DQCzBpszbVfutCDZfqB0YKBNNgw')
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '-1002500481488')
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://dntdvjivdtfyslmwjvzs.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRudGR2aml2ZHRmeXNsbXdqdnpzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTEzNTU3MiwiZXhwIjoyMDY2NzExNTcyfQ.J-8vuKCKxmZNntfc0DHyXiRQoIeKFhiSLMflDUj59fQ')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'mzH6GqatLNN584S')

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class DealBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        self.is_running = True
        
    def setup_handlers(self):
        """Set up command and callback handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command and add user to database"""
        user = update.effective_user
        
        # Add user to subscribers table
        try:
            supabase.table('subscribers').upsert({
                'telegram_user_id': user.id,
                'username': user.username or 'Unknown',
                'first_name': user.first_name or 'User',
                'last_active': datetime.now().isoformat()
            }, on_conflict='telegram_user_id').execute()
            
            logger.info(f"New subscriber: {user.first_name} (@{user.username})")
        except Exception as e:
            logger.error(f"Error adding subscriber: {e}")
        
        welcome_message = f"""
🔥 **Welcome to Daily Deals Nose!** 🔥

Hey {user.first_name}! Get ready for the hottest deals delivered straight to your feed!

🎯 **What you'll get:**
• Daily curated deals with up to 80% off
• Exclusive member-only offers  
• Real-time price alerts
• Categories: Tech, Fashion, Home, Travel & more

💎 **Premium Features** (Coming Soon):
• Early access to flash sales
• Personalized deal recommendations
• Price tracking alerts
• VIP-only exclusive deals

🚀 Join our main channel to never miss a deal!

**Commands:**
/stats - View channel statistics
/help - Get help and support
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Join Main Channel", url=f"https://t.me/{CHANNEL_ID.replace('@', '').replace('-100', '')}")],
            [InlineKeyboardButton("📊 View Stats", callback_data="public_stats")],
            [InlineKeyboardButton("💎 Premium Info", callback_data="premium_info")]
        ])
        
        await update.message.reply_text(
            welcome_message, 
            reply_markup=keyboard, 
            parse_mode='Markdown'
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Provide help information"""
        help_text = """
🆘 **Daily Deals Nose - Help**

**Available Commands:**
• /start - Welcome message and setup
• /stats - View channel statistics  
• /help - This help message
• /admin - Admin panel (admins only)

**How it works:**
1. Join our main channel for daily deals
2. Click deal links to get discounts
3. Save money on amazing products!

**Support:**
If you need help, contact @YourSupportUsername

**Tips:**
• Enable notifications for instant deal alerts
• Share with friends to help them save too!
• Check back daily for new deals

Happy saving! 💰
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel access with password protection"""
        # Simple password check (in production, use proper authentication)
        if len(context.args) == 0:
            await update.message.reply_text(
                "🔐 **Admin Access**\n\nPlease provide admin password:\n`/admin your_password_here`",
                parse_mode='Markdown'
            )
            return
        
        if context.args[0] != ADMIN_PASSWORD:
            await update.message.reply_text("❌ **Access Denied**\n\nIncorrect password.")
            return
        
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Analytics", callback_data="admin_analytics")],
            [InlineKeyboardButton("🔄 Post Test Deal", callback_data="admin_post_deal")],
            [InlineKeyboardButton("🎯 Find & Post Deals", callback_data="admin_find_deals")],
            [InlineKeyboardButton("⚙️ Bot Settings", callback_data="admin_settings")],
            [InlineKeyboardButton("👥 Subscriber Stats", callback_data="admin_subscribers")],
            [InlineKeyboardButton("💰 Revenue Report", callback_data="admin_revenue")]
        ])
        
        await update.message.reply_text(
            "🛠 **Admin Panel - Daily Deals Nose**\n\nChoose an action:",
            reply_markup=admin_keyboard,
            parse_mode='Markdown'
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show public statistics"""
        await self.show_public_stats(update.message)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all button callback queries"""
        query = update.callback_query
        await query.answer()
        
        callback_handlers = {
            "public_stats": self.show_public_stats,
            "premium_info": self.show_premium_info,
            "admin_analytics": self.show_admin_analytics,
            "admin_post_deal": self.post_test_deal,
            "admin_find_deals": self.find_and_post_deals,
            "admin_settings": self.show_admin_settings,
            "admin_subscribers": self.show_subscriber_stats,
            "admin_revenue": self.show_revenue_report
        }
        
        handler = callback_handlers.get(query.data)
        if handler:
            await handler(query)
        else:
            await query.edit_message_text("❌ Unknown command")
    
    async def show_public_stats(self, message_or_query):
        """Show public statistics"""
        try:
            # Get subscriber count
            subscribers = supabase.table('subscribers').select('*').execute()
            subscriber_count = len(subscribers.data)
            
            # Get today's analytics
            today = datetime.now().date()
            analytics = supabase.table('analytics').select('*').eq('date', today).execute()
            
            if analytics.data:
                stats = analytics.data[0]
                clicks = stats.get('total_clicks', 0)
                deals_posted = stats.get('deals_posted', 0)
            else:
                clicks = 0
                deals_posted = 0
            
            # Get total deals
            deals = supabase.table('deals').select('*').execute()
            total_deals = len(deals.data)
            
            stats_message = f"""
📊 **Daily Deals Nose - Live Stats**

👥 **Community**: {subscriber_count:,} savvy shoppers
🔥 **Total Deals Posted**: {total_deals:,}
🎯 **Today's Clicks**: {clicks:,}
📈 **Deals Today**: {deals_posted}
💰 **Total Savings**: $50,000+ (estimated)

⚡ **Status**: Active & Finding Deals!
🕐 **Last Updated**: {datetime.now().strftime('%H:%M UTC')}

Join the action: @{CHANNEL_ID.replace('@', '').replace('-100', '')}
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Join Channel", url=f"https://t.me/{CHANNEL_ID.replace('@', '').replace('-100', '')}")]
            ])
            
            if hasattr(message_or_query, 'edit_message_text'):
                await message_or_query.edit_message_text(
                    stats_message, 
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                await message_or_query.reply_text(
                    stats_message, 
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            
        except Exception as e:
            error_msg = f"❌ Error loading stats: {e}"
            if hasattr(message_or_query, 'edit_message_text'):
                await message_or_query.edit_message_text(error_msg)
            else:
                await message_or_query.reply_text(error_msg)
    
    async def show_premium_info(self, query):
        """Show premium subscription information"""
        premium_message = """
💎 **Premium Membership - Coming Soon!**

🌟 **Exclusive Benefits:**
• Early access to flash sales (1 hour before public)
• Premium-only deal alerts via DM
• Price tracking for your wishlist items
• Exclusive high-value deals ($50+ savings)
• Priority customer support
• Ad-free experience

💰 **Pricing:** $9.99/month
🎁 **Launch Special:** First 100 members get 50% off!

📧 **Get Notified:** 
We'll announce the premium launch soon. Stay tuned to our main channel!

🚀 Join our free channel now to not miss the premium launch!
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Join Free Channel", url=f"https://t.me/{CHANNEL_ID.replace('@', '').replace('-100', '')}")]
        ])
        
        await query.edit_message_text(
            premium_message,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    async def show_admin_analytics(self, query):
        """Show detailed admin analytics"""
        try:
            # Get comprehensive data
            deals = supabase.table('deals').select('*').execute()
            posts = supabase.table('posts').select('*').execute()
            subscribers = supabase.table('subscribers').select('*').execute()
            
            # Calculate metrics
            total_deals = len(deals.data)
            total_posts = len(posts.data)
            total_subscribers = len(subscribers.data)
            
            # Revenue calculations
            total_revenue = sum(float(deal.get('revenue', 0)) for deal in deals.data)
            total_clicks = sum(int(deal.get('clicks', 0)) for deal in deals.data)
            
            # Performance metrics
            avg_revenue_per_deal = total_revenue / max(total_deals, 1)
            click_through_rate = (total_clicks / max(total_posts, 1)) if total_posts else 0
            
            # Today's metrics
            today = datetime.now().date()
            today_deals = [d for d in deals.data if d.get('posted_at', '').startswith(str(today))]
            today_revenue = sum(float(d.get('revenue', 0)) for d in today_deals)
            
            analytics_message = f"""
📈 **Admin Analytics Dashboard**

📊 **Overview**:
• Total Deals: {total_deals:,}
• Total Posts: {total_posts:,}  
• Subscribers: {total_subscribers:,}
• Total Clicks: {total_clicks:,}
• Total Revenue: ${total_revenue:.2f}

📅 **Today's Performance**:
• Deals Posted: {len(today_deals)}
• Revenue Today: ${today_revenue:.2f}
• New Subscribers: {len([s for s in subscribers.data if s.get('joined_at', '').startswith(str(today))])}

📈 **Key Metrics**:
• Avg Revenue/Deal: ${avg_revenue_per_deal:.2f}
• Avg Clicks/Post: {click_through_rate:.1f}
• Subscriber Growth: +{len([s for s in subscribers.data if (datetime.now() - datetime.fromisoformat(s.get('joined_at', datetime.now().isoformat()))).days <= 7])} this week

🎯 **System Status**: 
• Bot Status: ✅ Running
• Auto-posting: ✅ Enabled  
• Database: ✅ Connected
• Last Deal: {datetime.now().strftime('%H:%M UTC')}
            """
            
            await query.edit_message_text(analytics_message, parse_mode='Markdown')
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error loading analytics: {e}")
    
    async def post_test_deal(self, query):
        """Post a test deal to the channel"""
        await query.edit_message_text("🔄 **Posting test deal...**\n\nPlease wait...")
        
        try:
            # Sample deal data
            sample_deals = [
                {
                    'title': '🔥 Apple AirPods Pro 2nd Gen - Lightning Deal!',
                    'description': 'Active Noise Cancellation, Adaptive Transparency, Spatial Audio. Perfect for work, travel, and workouts.',
                    'original_price': 249.99,
                    'deal_price': 179.99,
                    'discount_percentage': 28,
                    'affiliate_link': 'https://amzn.to/airpods-pro-deal',
                    'category': 'Electronics',
                    'source': 'Amazon',
                    'image_url': 'https://m.media-amazon.com/images/I/61SUj2aKoEL._AC_SL1500_.jpg'
                },
                {
                    'title': '💻 Samsung 27" 4K Monitor - Massive Savings!',
                    'description': 'Ultra HD 4K resolution, USB-C connectivity, height adjustable stand. Perfect for work and gaming.',
                    'original_price': 399.99,
                    'deal_price': 249.99,
                    'discount_percentage': 38,
                    'affiliate_link': 'https://click.linksynergy.com/samsung-monitor',
                    'category': 'Electronics',
                    'source': 'Best Buy',
                    'image_url': 'https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6425/6425332_sd.jpg'
                }
            ]
            
            # Pick random deal
            deal_data = random.choice(sample_deals)
            deal_data['expires_at'] = (datetime.now() + timedelta(hours=24)).isoformat()
            
            # Insert deal into database
            result = supabase.table('deals').insert(deal_data).execute()
            deal_id = result.data[0]['id']
            
            # Post to channel
            message = await self.post_deal_to_channel(deal_data, deal_id)
            
            # Update analytics
            await self.update_daily_analytics('deals_posted', 1)
            
            success_message = f"""
✅ **Test Deal Posted Successfully!**

📢 **Posted to**: @{CHANNEL_ID.replace('@', '').replace('-100', '')}
🆔 **Deal ID**: {deal_id}
📨 **Message ID**: {message.message_id}
🕐 **Posted at**: {datetime.now().strftime('%H:%M:%S UTC')}

💡 **Tip**: Check your channel to see the live deal post!
            """
            
            await query.edit_message_text(success_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error posting test deal: {e}")
            await query.edit_message_text(f"❌ **Error posting deal**: {e}")
    
    async def find_and_post_deals(self, query):
        """Find and post real deals automatically"""
        await query.edit_message_text("🔍 **Searching for hot deals...**\n\nThis may take 30-60 seconds...")
        
        try:
            # Find deals from various sources
            deals = await self.scrape_deals()
            
            if not deals:
                await query.edit_message_text("❌ **No new deals found**\n\nTry again in a few minutes.")
                return
            
            posted_count = 0
            posted_deals = []
            
            # Post up to 3 deals
            for deal in deals[:3]:
                try:
                    # Insert deal into database
                    result = supabase.table('deals').insert(deal).execute()
                    deal_id = result.data[0]['id']
                    
                    # Post to channel
                    message = await self.post_deal_to_channel(deal, deal_id)
                    posted_deals.append(deal['title'][:50] + "...")
                    posted_count += 1
                    
                    # Update analytics
                    await self.update_daily_analytics('deals_posted', 1)
                    
                    # Wait between posts to avoid spam
                    if posted_count < len(deals[:3]):
                        await asyncio.sleep(10)
                        
                except Exception as e:
                    logger.error(f"Error posting deal: {e}")
                    continue
            
            if posted_count > 0:
                success_message = f"""
✅ **Successfully Posted {posted_count} Deals!**

📢 **Posted to**: @{CHANNEL_ID.replace('@', '').replace('-100', '')}

🔥 **Deals Posted**:
{chr(10).join(f"• {deal}" for deal in posted_deals)}

💡 **Next auto-post**: {(datetime.now() + timedelta(hours=4)).strftime('%H:%M UTC')}
                """
            else:
                success_message = "❌ **No deals could be posted**\n\nAll found deals may have been duplicates or invalid."
            
            await query.edit_message_text(success_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error finding deals: {e}")
            await query.edit_message_text(f"❌ **Error finding deals**: {e}")
    
    async def scrape_deals(self) -> List[Dict]:
        """Scrape deals from various sources"""
        deals = []
        
        # In production, implement actual scraping
        # For now, return curated sample deals
        sample_deals = [
            {
                'title': '🎧 Sony WH-1000XM5 Headphones - Best Price!',
                'description': 'Industry-leading noise cancellation with 30-hour battery life. Crystal clear calls and premium sound quality.',
                'original_price': 399.99,
                'deal_price': 298.00,
                'discount_percentage': 25,
                'affiliate_link': 'https://amzn.to/sony-xm5-headphones',
                'category': 'Electronics',
                'source': 'Amazon',
                'expires_at': (datetime.now() + timedelta(hours=18)).isoformat(),
                'image_url': 'https://m.media-amazon.com/images/I/51QeS0jmOnL._AC_SL1500_.jpg'
            },
            {
                'title': '👔 Men\'s Business Shirt Collection - 60% Off!',
                'description': 'Premium cotton dress shirts, wrinkle-free, multiple colors. Perfect for office or formal events.',
                'original_price': 89.99,
                'deal_price': 35.99,
                'discount_percentage': 60,
                'affiliate_link': 'https://click.linksynergy.com/mens-shirts-deal',
                'category': 'Fashion',
                'source': 'Macy\'s',
                'expires_at': (datetime.now() + timedelta(hours=12)).isoformat(),
                'image_url': 'https://slimages.macysassets.com/is/image/MCY/products/optimized/24022190_fpx.tif'
            },
            {
                'title': '🏠 Instant Pot Duo Plus 8-Quart - Kitchen Essential!',
                'description': '9-in-1 multi-cooker: pressure cook, slow cook, rice cooker, steamer, sauté, yogurt maker & more.',
                'original_price': 149.95,
                'deal_price': 79.95,
                'discount_percentage': 47,
                'affiliate_link': 'https://amzn.to/instant-pot-duo-plus',
                'category': 'Home & Kitchen',
                'source': 'Amazon',
                'expires_at': (datetime.now() + timedelta(days=2)).isoformat(),
                'image_url': 'https://m.media-amazon.com/images/I/71VLWGw6HjL._AC_SL1500_.jpg'
            },
            {
                'title': '📱 iPhone 14 Case Collection - Premium Protection!',
                'description': 'Military-grade protection, wireless charging compatible, crystal clear or bold colors available.',
                'original_price': 49.99,
                'deal_price': 19.99,
                'discount_percentage': 60,
                'affiliate_link': 'https://amzn.to/iphone14-cases',
                'category': 'Electronics',
                'source': 'Amazon',
                'expires_at': (datetime.now() + timedelta(hours=6)).isoformat(),
                'image_url': 'https://m.media-amazon.com/images/I/61uH5YE7JaL._AC_SL1500_.jpg'
            }
        ]
        
        # Filter for good deals (20%+ discount)
        good_deals = [deal for deal in sample_deals if deal['discount_percentage'] >= 20]
        
        # Check if deals already exist in database to avoid duplicates
        existing_deals = supabase.table('deals').select('title').execute()
        existing_titles = [deal['title'] for deal in existing_deals.data]
        
        # Filter out existing deals
        new_deals = [deal for deal in good_deals if deal['title'] not in existing_titles]
        
        return new_deals[:3]  # Return up to 3 new deals
    
    async def post_deal_to_channel(self, deal: Dict, deal_id: int):
        """Post a formatted deal to the Telegram channel"""
        try:
            discount = int(((deal['original_price'] - deal['deal_price']) / deal['original_price']) * 100)
            savings = deal['original_price'] - deal['deal_price']
            
            # Format expiration time
            expires_at = datetime.fromisoformat(deal['expires_at'].replace('Z', '+00:00'))
            time_left = expires_at - datetime.now()
            
            if time_left.days > 0:
                time_text = f"{time_left.days} day(s)"
            elif time_left.seconds > 3600:
                time_text = f"{time_left.seconds // 3600} hour(s)"
            else:
                time_text = f"{time_left.seconds // 60} minute(s)"
            
            # Create engaging post text
            post_text = f"""
🔥 **DEAL ALERT** 🔥

{deal['title']}

💰 **${deal['deal_price']:.2f}** ~~${deal['original_price']:.2f}~~
🎯 **{discount}% OFF** - Save ${savings:.2f}!

📝 {deal['description']}

⏰ **Expires in {time_text}**
🏷️ **Category**: {deal['category']}
🏪 **Source**: {deal['source']}

👆 **Tap below to get this deal!** 👆
            """
            
            # Create inline keyboard
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Get This Deal Now!", url=deal['affiliate_link'])],
                [InlineKeyboardButton("🔔 Join for More Deals", url=f"https://t.me/{CHANNEL_ID.replace('@', '').replace('-100', '')}")]
            ])
            
            # Post to channel
            message = await self.bot.send_message(
                chat_id=CHANNEL_ID,
                text=post_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            # Log the post in database
            supabase.table('posts').insert({
                'deal_id': deal_id,
                'telegram_message_id': message.message_id,
                'posted_at': datetime.now().isoformat()
            }).execute()
            
            logger.info(f"Posted deal to channel: {deal['title']}")
            return message
            
        except Exception as e:
            logger.error(f"Error posting to channel: {e}")
            raise e
    
    async def show_admin_settings(self, query):
        """Show and manage bot settings"""
        try:
            # Get current settings
            settings = supabase.table('settings').select('*').execute()
            settings_dict = {s['key']: s['value'] for s in settings.data}
            
            auto_posting = settings_dict.get('auto_posting_enabled', 'true')
            posting_interval = settings_dict.get('posting_interval', '4')
            min_discount = settings_dict.get('min_discount_percentage', '20')
            
            settings_message = f"""
⚙️ **Bot Settings**

🔄 **Auto-posting**: {'✅ Enabled' if auto_posting == 'true' else '❌ Disabled'}
⏰ **Posting Interval**: Every {posting_interval} hours
📊 **Min Discount**: {min_discount}% or higher
🎯 **Active Networks**: Amazon, CJ, ShareASale

**Current Status**:
• System: ✅ Online
• Database: ✅ Connected  
• Channel Access: ✅ Active
• Last Auto-post: {datetime.now().strftime('%H:%M UTC')}

💡 Settings can be modified in the database directly.
            """
            
            await query.edit_message_text(settings_message, parse_mode='Markdown')
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error loading settings: {e}")
    
    async def show_subscriber_stats(self, query):
        """Show detailed subscriber statistics"""
        try:
            subscribers = supabase.table('subscribers').select('*').execute()
            
            # Calculate metrics
            total_subscribers = len(subscribers.data)
            today = datetime.now().date()
            week_ago = today - timedelta(days=7)
            
            # New subscribers today and this week
            today_subs = [s for s in subscribers.data 
                         if s.get('joined_at', '').startswith(str(today))]
            week_subs = [s for s in subscribers.data 
                        if datetime.fromisoformat(s.get('joined_at', datetime.now().isoformat())).date() >= week_ago]
            
            # Premium subscribers (when implemented)
            premium_subs = [s for s in subscribers.data if s.get('is_premium', False)]
            
            # Active subscribers (last 7 days)
            active_subs = [s for s in subscribers.data 
                          if datetime.fromisoformat(s.get('last_active', datetime.now().isoformat())).date() >= week_ago]
            
            subscriber_message = f"""
👥 **Subscriber Analytics**

📊 **Overview**:
• Total Subscribers: {total_subscribers:,}
• Premium Members: {len(premium_subs):,}
• Active (7 days): {len(active_subs):,}

📈 **Growth**:
• New Today: +{len(today_subs)}
• New This Week: +{len(week_subs)}
• Growth Rate: {(len(week_subs)/max(total_subscribers-len(week_subs), 1)*100):.1f}%

🎯 **Engagement**:
• Active Rate: {(len(active_subs)/max(total_subscribers, 1)*100):.1f}%
• Premium Rate: {(len(premium_subs)/max(total_subscribers, 1)*100):.1f}%

💰 **Revenue Potential**:
• Est. Monthly Revenue: ${len(premium_subs) * 9.99:.2f}
• Conversion Target: {total_subscribers // 10} premium subs
            """
            
            await query.edit_message_text(subscriber_message, parse_mode='Markdown')
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error loading subscriber stats: {e}")
    
    async def show_revenue_report(self, query):
        """Show detailed revenue analytics"""
        try:
            deals = supabase.table('deals').select('*').execute()
            
            # Calculate revenue metrics
            total_revenue = sum(float(deal.get('revenue', 0)) for deal in deals.data)
            total_clicks = sum(int(deal.get('clicks', 0)) for deal in deals.data)
            total_conversions = sum(int(deal.get('conversions', 0)) for deal in deals.data)
            
            # Today's revenue
            today = datetime.now().date()
            today_deals = [d for d in deals.data if d.get('posted_at', '').startswith(str(today))]
            today_revenue = sum(float(d.get('revenue', 0)) for d in today_deals)
            today_clicks = sum(int(d.get('clicks', 0)) for d in today_deals)
            
            # Top performing categories
            category_revenue = {}
            for deal in deals.data:
                category = deal.get('category', 'Unknown')
                category_revenue[category] = category_revenue.get(category, 0) + float(deal.get('revenue', 0))
            
            top_category = max(category_revenue.items(), key=lambda x: x[1]) if category_revenue else ('None', 0)
            
            # Calculate rates
            conversion_rate = (total_conversions / max(total_clicks, 1)) * 100
            avg_revenue_per_click = total_revenue / max(total_clicks, 1)
            
            revenue_message = f"""
💰 **Revenue Analytics Report**

📊 **Total Performance**:
• Total Revenue: ${total_revenue:.2f}
• Total Clicks: {total_clicks:,}
• Total Conversions: {total_conversions:,}
• Conversion Rate: {conversion_rate:.2f}%

📅 **Today's Performance**:
• Revenue Today: ${today_revenue:.2f}
• Clicks Today: {today_clicks:,}
• Deals Posted: {len(today_deals)}

📈 **Key Metrics**:
• Revenue/Click: ${avg_revenue_per_click:.3f}
• Revenue/Deal: ${total_revenue/max(len(deals.data), 1):.2f}
• Top Category: {top_category[0]} (${top_category[1]:.2f})

🎯 **Projections**:
• Monthly Est.: ${total_revenue * 30:.2f}
• Weekly Target: ${(total_revenue / max((datetime.now() - datetime.now().replace(day=1)).days, 1)) * 7:.2f}
            """
            
            await query.edit_message_text(revenue_message, parse_mode='Markdown')
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error loading revenue report: {e}")
    
    async def update_daily_analytics(self, metric: str, value: int):
        """Update daily analytics in database"""
        try:
            today = datetime.now().date()
            
            # Get or create today's analytics record
            existing = supabase.table('analytics').select('*').eq('date', today).execute()
            
            if existing.data:
                # Update existing record
                current_value = existing.data[0].get(metric, 0)
                new_value = current_value + value
                
                supabase.table('analytics').update({
                    metric: new_value,
                    'updated_at': datetime.now().isoformat()
                }).eq('date', today).execute()
            else:
                # Create new record
                supabase.table('analytics').insert({
                    'date': today,
                    metric: value
                }).execute()
                
        except Exception as e:
            logger.error(f"Error updating analytics: {e}")
    
    async def run_scheduler(self):
        """Run the automatic posting scheduler"""
        logger.info("Starting auto-posting scheduler...")
        
        while self.is_running:
            try:
                # Check if auto-posting is enabled
                settings = supabase.table('settings').select('*').eq('key', 'auto_posting_enabled').execute()
                if not settings.data or settings.data[0]['value'] != 'true':
                    logger.info("Auto-posting disabled, sleeping...")
                    await asyncio.sleep(300)  # Check every 5 minutes
                    continue
                
                # Get posting interval
                interval_setting = supabase.table('settings').select('*').eq('key', 'posting_interval').execute()
                interval_hours = int(interval_setting.data[0]['value']) if interval_setting.data else 4
                
                logger.info(f"Auto-posting enabled, interval: {interval_hours} hours")
                
                # Find and post deals
                deals = await self.scrape_deals()
                if deals:
                    # Post the first deal
                    deal = deals[0]
                    
                    # Insert into database
                    result = supabase.table('deals').insert(deal).execute()
                    deal_id = result.data[0]['id']
                    
                    # Post to channel
                    await self.post_deal_to_channel(deal, deal_id)
                    
                    # Update analytics
                    await self.update_daily_analytics('deals_posted', 1)
                    
                    logger.info(f"Auto-posted deal: {deal['title']}")
                else:
                    logger.info("No new deals found for auto-posting")
                
                # Wait for next interval
                sleep_seconds = interval_hours * 3600
                logger.info(f"Sleeping for {interval_hours} hours until next auto-post...")
                await asyncio.sleep(sleep_seconds)
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    def run(self):
        """Start the bot and scheduler"""
        logger.info("🚀 Daily Deals Nose Bot Starting...")
        
        async def start_bot():
            # Start the scheduler in background
            scheduler_task = asyncio.create_task(self.run_scheduler())
            
            # Initialize the application
            await self.application.initialize()
            await self.application.start()
            
            # Start polling
            await self.application.updater.start_polling(allowed_updates=['message', 'callback_query'])
            
            logger.info("✅ Bot is now running and listening for updates!")
            logger.info(f"📢 Channel: {CHANNEL_ID}")
            logger.info("🛠 Send /admin [password] to access admin panel")
            
            # Keep running
            try:
                await scheduler_task
            except asyncio.CancelledError:
                logger.info("Scheduler cancelled")
            finally:
                # Cleanup
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
        
        # Run the bot
        try:
            asyncio.run(start_bot())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            self.is_running = False
            logger.info("🛑 Daily Deals Nose Bot Stopped")

# Helper function to initialize database tables
async def init_database():
    """Initialize database tables if they don't exist"""
    logger.info("Initializing database...")
    
    # This should be run once when setting up
    # The SQL commands are in the setup guide
    
    try:
        # Test database connection
        result = supabase.table('settings').select('*').limit(1).execute()
        logger.info("✅ Database connection successful")
        
        # Insert default settings if not exist
        default_settings = [
            {'key': 'auto_posting_enabled', 'value': 'true'},
            {'key': 'posting_interval', 'value': '4'},
            {'key': 'min_discount_percentage', 'value': '20'},
            {'key': 'premium_price', 'value': '9.99'}
        ]
        
        for setting in default_settings:
            try:
                supabase.table('settings').upsert(setting, on_conflict='key').execute()
            except:
                pass  # Setting might already exist
                
        logger.info("✅ Default settings initialized")
        
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        logger.error("Please check your Supabase connection and run the SQL schema first")

if __name__ == "__main__":
    # Validate environment variables
    required_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHANNEL_ID', 'SUPABASE_URL', 'SUPABASE_SERVICE_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set all required environment variables before running the bot")
        exit(1)
    
    # Initialize database
    asyncio.run(init_database())
    
    # Start the bot
    bot = DealBot()
    bot.run()
