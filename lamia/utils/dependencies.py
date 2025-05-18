import subprocess
import sys
import importlib
from typing import Optional, Dict, Any, Tuple   

def ensure_package(package_name: str, min_version: Optional[str] = None) -> Tuple[bool, str]:
    """
    Ensure a package is installed, installing it if necessary.
    
    Args:
        package_name: Name of the package to check/install
        min_version: Minimum version required (optional)
        
    Returns:
        Tuple[bool, str]: (Success status, Error message if any)
    """
    package_spec = f"{package_name}>={min_version}" if min_version else package_name
    
    try:
        # Try importing first
        importlib.import_module(package_name)
        return True, ""
    except ImportError:
        print(f"\n{package_name} package not found. Installing {package_spec}...")
        
        try:
            # Install the package using pip
            subprocess.check_call([
                sys.executable, 
                "-m", 
                "pip", 
                "install", 
                "--quiet",
                package_spec
            ])
            
            # Try importing again to verify
            importlib.import_module(package_name)
            print(f"Successfully installed {package_spec}")
            return True, ""
            
        except (subprocess.CalledProcessError, ImportError) as e:
            error_msg = (
                f"Failed to install {package_spec}. "
                f"Please install it manually: pip install {package_spec}"
            )
            return False, error_msg

def import_optional(
    package_name: str,
    min_version: Optional[str] = None,
    fallback_module: Optional[str] = None
) -> Tuple[Optional[Any], bool, str]:
    """
    Import a package, installing it if necessary, with optional fallback.
    
    Args:
        package_name: Name of the package to import
        min_version: Minimum version required
        fallback_module: Name of fallback module to import if package install fails
        
    Returns:
        Tuple[Optional[module], bool, str]: (Imported module or None, Success status, Error message if any)
    """
    # Try to ensure the package is installed
    success, error_msg = ensure_package(package_name, min_version)
    
    if success:
        try:
            module = importlib.import_module(package_name)
            return module, True, ""
        except ImportError as e:
            error_msg = f"Failed to import {package_name}: {str(e)}"
    
    # If we have a fallback and the main package failed, try that
    if fallback_module and not success:
        try:
            module = importlib.import_module(fallback_module)
            return module, True, ""
        except ImportError as e:
            error_msg += f"\nFallback also failed: {str(e)}"
    
    return None, False, error_msg 