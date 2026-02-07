"""File system operations with excellent IntelliSense support."""

import json


class FileActions:
    """File system operations with excellent IntelliSense support.

    Access via: file.read(), file.write(), file.append()
    """

    def read(self, path: str, encoding: str = "utf-8") -> str:
        """Read file contents.

        Args:
            path: File path to read
            encoding: File encoding (default: utf-8)

        Returns:
            Command string for lamia.run() to execute

        Example:
            content = file.read("/path/to/file.txt")
            data = file.read("config.json")
        """
        cmd_parts = [f"file://read:{path}"]
        if encoding != "utf-8":
            cmd_parts.append(f"encoding:{encoding}")
        return " ".join(cmd_parts)

    def write(self, path: str, content: str, encoding: str = "utf-8") -> str:
        """Write content to file (creates new or overwrites existing).

        Args:
            path: File path to write
            content: Content to write
            encoding: File encoding (default: utf-8)
        Returns:
            Command string for lamia.run() to execute

        Example:
            file.write("/path/to/file.txt", "Hello, World!")
            file.write("output.json", json.dumps(data))
        """
        cmd_parts = [f"file://write:{path}"]
        cmd_parts.append(f"content:{json.dumps(content)}")
        if encoding != "utf-8":
            cmd_parts.append(f"encoding:{encoding}")
        return " ".join(cmd_parts)

    def append(self, path: str, content: str, encoding: str = "utf-8") -> str:
        """Append content to file.

        Args:
            path: File path to append to
            content: Content to append
            encoding: File encoding (default: utf-8)
        Returns:
            Command string for lamia.run() to execute

        Example:
            file.append("/var/log/app.log", "New log entry\\n")
            file.append("notes.txt", "Additional note")
        """
        cmd_parts = [f"file://append:{path}"]
        cmd_parts.append(f"content:{json.dumps(content)}")
        if encoding != "utf-8":
            cmd_parts.append(f"encoding:{encoding}")
        return " ".join(cmd_parts)

# Create singleton instance for import
file = FileActions()