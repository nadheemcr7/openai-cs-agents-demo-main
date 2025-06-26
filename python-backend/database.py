import os
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")
        
        self.supabase: Client = create_client(url, key)
    
    async def get_customer_by_account_number(self, account_number: str) -> Optional[Dict[str, Any]]:
        """Get customer details by account number"""
        try:
            response = self.supabase.table("customers").select("*").eq("account_number", account_number).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching customer: {e}")
            return None
    
    async def get_booking_by_confirmation(self, confirmation_number: str) -> Optional[Dict[str, Any]]:
        """Get booking details with customer and flight info"""
        try:
            response = self.supabase.table("bookings").select("""
                *,
                customers:customer_id(*),
                flights:flight_id(*)
            """).eq("confirmation_number", confirmation_number).execute()
            
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching booking: {e}")
            return None
    
    async def get_flight_status(self, flight_number: str) -> Optional[Dict[str, Any]]:
        """Get flight status information"""
        try:
            response = self.supabase.table("flights").select("*").eq("flight_number", flight_number).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching flight: {e}")
            return None
    
    async def update_seat_number(self, confirmation_number: str, new_seat: str) -> bool:
        """Update seat number for a booking"""
        try:
            response = self.supabase.table("bookings").update({
                "seat_number": new_seat
            }).eq("confirmation_number", confirmation_number).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error updating seat: {e}")
            return False
    
    async def cancel_booking(self, confirmation_number: str) -> bool:
        """Cancel a booking"""
        try:
            response = self.supabase.table("bookings").update({
                "booking_status": "Cancelled"
            }).eq("confirmation_number", confirmation_number).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error cancelling booking: {e}")
            return False
    
    async def get_customer_bookings(self, account_number: str) -> List[Dict[str, Any]]:
        """Get all bookings for a customer"""
        try:
            response = self.supabase.table("bookings").select("""
                *,
                flights:flight_id(*)
            """).eq("customers.account_number", account_number).execute()
            
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching customer bookings: {e}")
            return []
    
    async def save_conversation(self, session_id: str, history: List[Dict], context: Dict, current_agent: str):
        """Save conversation state to database"""
        try:
            data = {
                "session_id": session_id,
                "history": history,
                "context": context,
                "current_agent": current_agent,
                "last_updated": "now()"
            }
            
            response = self.supabase.table("conversations").upsert(data).execute()
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return False
    
    async def load_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load conversation state from database"""
        try:
            response = self.supabase.table("conversations").select("*").eq("session_id", session_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error loading conversation: {e}")
            return None

# Global instance
db_client = SupabaseClient()