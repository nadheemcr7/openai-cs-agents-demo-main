import os
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class MockDatabase:
    """Mock database for demo purposes when Supabase is not available"""
    
    def __init__(self):
        self.customers = {
            "CUST001": {
                "id": "1",
                "account_number": "CUST001",
                "name": "John Smith",
                "email": "john.smith@email.com"
            },
            "CUST002": {
                "id": "2", 
                "account_number": "CUST002",
                "name": "Jane Doe",
                "email": "jane.doe@email.com"
            },
            "CUST003": {
                "id": "3",
                "account_number": "CUST003", 
                "name": "Bob Johnson",
                "email": "bob.johnson@email.com"
            }
        }
        
        self.bookings = {
            "ABC123": {
                "id": "1",
                "confirmation_number": "ABC123",
                "customer_id": "1",
                "flight_id": "1",
                "seat_number": "12A",
                "booking_status": "Confirmed",
                "customers": self.customers["CUST001"],
                "flights": {
                    "id": "1",
                    "flight_number": "AA101",
                    "departure_time": "2024-01-15T10:00:00Z",
                    "arrival_time": "2024-01-15T14:00:00Z"
                }
            },
            "DEF456": {
                "id": "2",
                "confirmation_number": "DEF456", 
                "customer_id": "2",
                "flight_id": "2",
                "seat_number": "8C",
                "booking_status": "Confirmed",
                "customers": self.customers["CUST002"],
                "flights": {
                    "id": "2",
                    "flight_number": "AA202",
                    "departure_time": "2024-01-16T15:00:00Z",
                    "arrival_time": "2024-01-16T19:00:00Z"
                }
            }
        }
        
        self.flights = {
            "AA101": {
                "id": "1",
                "flight_number": "AA101",
                "current_status": "On Time",
                "gate": "A12",
                "terminal": "1",
                "delay_minutes": None
            },
            "AA202": {
                "id": "2", 
                "flight_number": "AA202",
                "current_status": "Delayed",
                "gate": "B5",
                "terminal": "2", 
                "delay_minutes": 30
            }
        }
        
        self.conversations = {}
    
    async def get_customer_by_account_number(self, account_number: str) -> Optional[Dict[str, Any]]:
        return self.customers.get(account_number)
    
    async def get_booking_by_confirmation(self, confirmation_number: str) -> Optional[Dict[str, Any]]:
        return self.bookings.get(confirmation_number)
    
    async def get_flight_status(self, flight_number: str) -> Optional[Dict[str, Any]]:
        return self.flights.get(flight_number)
    
    async def update_seat_number(self, confirmation_number: str, new_seat: str) -> bool:
        if confirmation_number in self.bookings:
            self.bookings[confirmation_number]["seat_number"] = new_seat
            return True
        return False
    
    async def cancel_booking(self, confirmation_number: str) -> bool:
        if confirmation_number in self.bookings:
            self.bookings[confirmation_number]["booking_status"] = "Cancelled"
            return True
        return False
    
    async def get_customer_bookings(self, account_number: str) -> List[Dict[str, Any]]:
        customer = self.customers.get(account_number)
        if not customer:
            return []
        
        customer_id = customer["id"]
        bookings = []
        for booking in self.bookings.values():
            if booking["customer_id"] == customer_id:
                bookings.append(booking)
        return bookings
    
    async def save_conversation(self, session_id: str, history: List[Dict], context: Dict, current_agent: str):
        self.conversations[session_id] = {
            "session_id": session_id,
            "history": history,
            "context": context,
            "current_agent": current_agent
        }
        return True
    
    async def load_conversation(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.conversations.get(session_id)

class SupabaseClient:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        
        if not url or not key:
            logger.warning("SUPABASE_URL and SUPABASE_ANON_KEY not found, using mock database")
            self.use_mock = True
            self.mock_db = MockDatabase()
            return
        
        try:
            self.supabase: Client = create_client(url, key)
            self.use_mock = False
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self.use_mock = True
            self.mock_db = MockDatabase()
    
    async def get_customer_by_account_number(self, account_number: str) -> Optional[Dict[str, Any]]:
        if self.use_mock:
            return await self.mock_db.get_customer_by_account_number(account_number)
        
        try:
            response = self.supabase.table("customers").select("*").eq("account_number", account_number).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching customer: {e}")
            return None
    
    async def get_booking_by_confirmation(self, confirmation_number: str) -> Optional[Dict[str, Any]]:
        if self.use_mock:
            return await self.mock_db.get_booking_by_confirmation(confirmation_number)
        
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
        if self.use_mock:
            return await self.mock_db.get_flight_status(flight_number)
        
        try:
            response = self.supabase.table("flights").select("*").eq("flight_number", flight_number).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching flight: {e}")
            return None
    
    async def update_seat_number(self, confirmation_number: str, new_seat: str) -> bool:
        if self.use_mock:
            return await self.mock_db.update_seat_number(confirmation_number, new_seat)
        
        try:
            response = self.supabase.table("bookings").update({
                "seat_number": new_seat
            }).eq("confirmation_number", confirmation_number).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error updating seat: {e}")
            return False
    
    async def cancel_booking(self, confirmation_number: str) -> bool:
        if self.use_mock:
            return await self.mock_db.cancel_booking(confirmation_number)
        
        try:
            response = self.supabase.table("bookings").update({
                "booking_status": "Cancelled"
            }).eq("confirmation_number", confirmation_number).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error cancelling booking: {e}")
            return False
    
    async def get_customer_bookings(self, account_number: str) -> List[Dict[str, Any]]:
        if self.use_mock:
            return await self.mock_db.get_customer_bookings(account_number)
        
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
        if self.use_mock:
            return await self.mock_db.save_conversation(session_id, history, context, current_agent)
        
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
        if self.use_mock:
            return await self.mock_db.load_conversation(session_id)
        
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