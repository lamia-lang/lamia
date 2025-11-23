"""HTTP request actions with excellent IntelliSense support."""

from typing import Optional
from lamia.internal_types import HttpAction, HttpActionType, HttpActionParams


class HttpActions:
    """HTTP request actions with excellent IntelliSense support.
    
    Access via: http.get(), http.post(), http.put(), etc.
    """
    
    def get(self, url: str, headers: Optional[dict] = None, params: Optional[dict] = None) -> HttpAction:
        """Send HTTP GET request.
        
        Args:
            url: Target URL
            headers: Optional HTTP headers dictionary
            params: Optional query parameters dictionary
            
        Returns:
            HttpAction configured for GET request
            
        Example:
            http.get("https://api.example.com/users", params={"page": 1})
        """
        return HttpAction(
            action=HttpActionType.GET,
            params=HttpActionParams(
                url=url,
                headers=headers,
                params=params
            )
        )
    
    def post(self, url: str, data=None, headers: Optional[dict] = None) -> HttpAction:
        """Send HTTP POST request.
        
        Args:
            url: Target URL
            data: Request body - dict for JSON, str for form data
            headers: Optional HTTP headers dictionary
            
        Returns:
            HttpAction configured for POST request
            
        Example:
            http.post("https://api.example.com/users", data={"name": "John"})
        """
        return HttpAction(
            action=HttpActionType.POST,
            params=HttpActionParams(
                url=url,
                data=data,
                headers=headers
            )
        )
    
    def put(self, url: str, data=None, headers: Optional[dict] = None) -> HttpAction:
        """Send HTTP PUT request.
        
        Args:
            url: Target URL
            data: Request body - dict for JSON, str for form data
            headers: Optional HTTP headers dictionary
            
        Returns:
            HttpAction configured for PUT request
            
        Example:
            http.put("https://api.example.com/users/123", data={"name": "Jane"})
        """
        return HttpAction(
            action=HttpActionType.PUT,
            params=HttpActionParams(
                url=url,
                data=data,
                headers=headers
            )
        )
    
    def patch(self, url: str, data=None, headers: Optional[dict] = None) -> HttpAction:
        """Send HTTP PATCH request.
        
        Args:
            url: Target URL
            data: Request body - dict for JSON, str for form data
            headers: Optional HTTP headers dictionary
            
        Returns:
            HttpAction configured for PATCH request
            
        Example:
            http.patch("https://api.example.com/users/123", data={"email": "new@example.com"})
        """
        return HttpAction(
            action=HttpActionType.PATCH,
            params=HttpActionParams(
                url=url,
                data=data,
                headers=headers
            )
        )
    
    def delete(self, url: str, headers: Optional[dict] = None) -> HttpAction:
        """Send HTTP DELETE request.
        
        Args:
            url: Target URL
            headers: Optional HTTP headers dictionary
            
        Returns:
            HttpAction configured for DELETE request
            
        Example:
            http.delete("https://api.example.com/users/123")
        """
        return HttpAction(
            action=HttpActionType.DELETE,
            params=HttpActionParams(
                url=url,
                headers=headers
            )
        )
    
    def head(self, url: str, headers: Optional[dict] = None) -> HttpAction:
        """Send HTTP HEAD request to get headers without body.
        
        Args:
            url: Target URL
            headers: Optional HTTP headers dictionary
            
        Returns:
            HttpAction configured for HEAD request
            
        Example:
            http.head("https://api.example.com/users/123")
        """
        return HttpAction(
            action=HttpActionType.HEAD,
            params=HttpActionParams(
                url=url,
                headers=headers
            )
        )
    
    def options(self, url: str, headers: Optional[dict] = None) -> HttpAction:
        """Send HTTP OPTIONS request to check allowed methods.
        
        Args:
            url: Target URL
            headers: Optional HTTP headers dictionary
            
        Returns:
            HttpAction configured for OPTIONS request
            
        Example:
            http.options("https://api.example.com/users")
        """
        return HttpAction(
            action=HttpActionType.OPTIONS,
            params=HttpActionParams(
                url=url,
                headers=headers
            )
        )