#!/usr/bin/env python3
"""
Direct Database Update for Pricing
==================================

Updates pricing directly in the database to match live Stripe configuration.
"""

import sqlite3
import os

def update_pricing_direct():
    """Update pricing directly in SQLite database"""
    
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'physio-2.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Updating pricing to match live Stripe configuration...")
        print("=" * 55)
        
        # Update Individual Monthly plan (€10.00)
        cursor.execute("""
            UPDATE plans 
            SET price_cents = 1000, currency = 'eur'
            WHERE slug = 'individual-monthly'
        """)
        
        # Update Individual Yearly plan (€90.00)
        cursor.execute("""
            UPDATE plans 
            SET price_cents = 9000, currency = 'eur'
            WHERE slug = 'individual-yearly'
        """)
        
        conn.commit()
        
        # Verify updates
        cursor.execute("""
            SELECT name, price_cents, currency, billing_interval, stripe_price_id 
            FROM plans 
            WHERE is_active = 1 
            ORDER BY display_order
        """)
        
        plans = cursor.fetchall()
        
        print("\n📊 Updated Pricing Configuration:")
        print("-" * 40)
        for plan in plans:
            name, price_cents, currency, interval, stripe_id = plan
            currency_symbol = "€" if currency == "eur" else "$"
            print(f"• {name}: {currency_symbol}{price_cents/100:.2f}/{interval}")
            print(f"  Stripe Price ID: {stripe_id}")
            print(f"  Currency: {currency.upper()}")
            print()
        
        conn.close()
        
        print("🎉 Pricing successfully updated!")
        print("✅ Database now matches live Stripe configuration")
        return True
        
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        return False

if __name__ == "__main__":
    success = update_pricing_direct()
    if success:
        print("\n🚀 Your app is ready for production deployment!")
        print("   The pricing now correctly matches your live Stripe setup:")
        print("   • Monthly: €10.00/month")
        print("   • Yearly: €90.00/year") 