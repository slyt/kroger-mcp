import os
from dotenv import load_dotenv
import logging
import httpx
import time
import json

from typing import List, Dict, Optional, Any
from pydantic import BaseModel

from mcp.server.fastmcp import FastMCP


# Initialize FastMCP server
mcp = FastMCP("kroger")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s - %(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()

class KrogerProduct(BaseModel):
    """Represents a product from the Kroger API."""
    product_id: str
    description: str
    brand: Optional[str]
    price: float
    aisle_location: Optional[str]
    upc: Optional[str]

class KrogerAPI:
    """Handles authentication and API calls to Kroger."""
    
    def __init__(self):
        self.client_id = os.getenv("KROGER_CLIENT_ID")
        self.client_secret = os.getenv("KROGER_CLIENT_SECRET")
        self.base_url = "https://api.kroger.com/v1"
        self.access_token = None
        self.token_expires_at = None
        self.location_id = None
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Kroger API credentials not found in environment variables")
    
    def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self.access_token and self.token_expires_at and self.token_expires_at > time.time():
            return self.access_token
            
        # Get new token
        auth_url = "https://api.kroger.com/v1/connect/oauth2/token"
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "product.compact"  # Scope for product information
        }
        
        response = httpx.post(auth_url, data=auth_data)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_expires_at = time.time() + token_data["expires_in"]
        
        return self.access_token
    
    def get_nearest_store_information(self, zip_code: str = "39180") -> str:
    
    
        """Get the location ID for a given zip code."""
        logger.info(f"Getting location ID for zip code: {zip_code}")
        
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        params = {
            "filter.zipCode.near": zip_code
        }
        
        url = f"{self.base_url}/locations"
        logger.debug(f"Making request to: {url}")
        
        try:
            response = httpx.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Locations response:\n{json.dumps(data, indent=2)}")
            
            if not data.get("data"):
                raise ValueError(f"No locations found for zip code: {zip_code}")
            
            # Use the first location
            location = data["data"][0]
            return location
            # self.location_id = location["locationId"]
            # logger.info(f"Found location ID: {self.location_id}")
            # return self.location_id
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get location: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            raise

    def search_products(self, store_id: str, query: str, limit: int = 10) -> List[KrogerProduct]:
        """Search for products using the Kroger API."""
        logger.info(f"Searching for products with query: {query}")
        
        token = self.get_access_token()
        logger.debug(f"Got access token: {token[:10]}...")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        logger.debug(f"Request headers: {headers}")
        
        params = {
            "filter.term": query,
            "filter.limit": limit,  # Limit results
            "filter.locationId": store_id  # Add location ID to get prices
        }
        logger.debug(f"Request params: {params}")
        
        url = f"{self.base_url}/products"
        logger.debug(f"Making request to: {url}")
        
        try:
            response = httpx.get(
                url,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            logger.info(f"Request successful with status code: {response.status_code}")
            
            data = response.json()
            logger.debug(f"Raw API response:\n{json.dumps(data, indent=2)}")
            return data.get("data", [])
            
        except httpx.HTTPStatusError as e:
            logger.error(f"API request failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in search_products: {str(e)}")
            raise

@mcp.tool()
async def get_nearest_store_information_mcp(zip_code: str = "80446") -> str:
    """Get information about the nearest Kroger grocery store for a given zip code.
    Args:
        zip_code: The zip code to get the nearest store information for.
    Returns:
        Information about the nearest Kroger grocery store.
    """
    kroger = KrogerAPI()
    return str(kroger.get_nearest_store_information(zip_code))

@mcp.tool()
async def search_products_mcp(store_id: str, query: str, limit: int = 10) -> str:
    """Search for products using the Kroger API."""
    kroger = KrogerAPI()
    return str(kroger.search_products(store_id, query, limit))

if __name__ == "__main__":
    # kroger = KrogerAPI()
    # location_data = kroger.get_location_id(zip_code="80446")
    mcp.run(transport="stdio")