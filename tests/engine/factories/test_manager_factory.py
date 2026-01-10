"""Tests for ManagerFactory."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from lamia.engine.factories.manager_factory import ManagerFactory
from lamia.engine.config_provider import ConfigProvider
from lamia.interpreter.command_types import CommandType
from lamia.engine.managers import Manager
from lamia.engine.managers.llm.llm_manager import LLMManager
from lamia.engine.managers.fs_manager import FSManager
from lamia.engine.managers.web import WebManager


class TestManagerFactoryInitialization:
    """Test ManagerFactory initialization."""
    
    def test_initialization_with_config_provider(self):
        """Test initialization with config provider."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        factory = ManagerFactory(config_provider)
        
        assert factory.config_provider == config_provider
        assert isinstance(factory._manager_registry, dict)
        assert isinstance(factory._manager_instances, dict)
        assert len(factory._manager_instances) == 0  # No instances created yet
    
    def test_manager_registry_initialization(self):
        """Test that manager registry is properly initialized."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        
        factory = ManagerFactory(config_provider)
        
        # Check that all command types are registered
        assert CommandType.LLM in factory._manager_registry
        assert CommandType.FILESYSTEM in factory._manager_registry
        assert CommandType.WEB in factory._manager_registry
        
        # Check that correct manager classes are registered
        assert factory._manager_registry[CommandType.LLM] == LLMManager
        assert factory._manager_registry[CommandType.FILESYSTEM] == FSManager
        assert factory._manager_registry[CommandType.WEB] == WebManager


class TestManagerFactoryManagerCreation:
    """Test manager creation and retrieval."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.factory = ManagerFactory(self.config_provider)
    
    def test_get_manager_creates_real_instance(self):
        """Test getting managers creates real instances."""
        # Test with real managers to verify basic functionality
        with patch.object(LLMManager, '__init__', return_value=None) as mock_init:
            manager = self.factory.get_manager(CommandType.LLM)
            
            # Should create instance and pass config
            mock_init.assert_called_once_with(self.config_provider)
            assert isinstance(manager, LLMManager)
            
            # Should be cached
            assert self.factory._manager_instances[CommandType.LLM] == manager
    
    def test_get_manager_with_mocked_class(self):
        """Test getting manager with mocked class for detailed verification."""
        mock_manager_class = Mock()
        mock_manager_instance = Mock(spec=Manager)
        mock_manager_class.return_value = mock_manager_instance
        
        # Replace the class in the registry
        self.factory._manager_registry[CommandType.LLM] = mock_manager_class
        
        manager = self.factory.get_manager(CommandType.LLM)
        
        # Should create new instance
        mock_manager_class.assert_called_once_with(self.config_provider)
        assert manager == mock_manager_instance
        
        # Should be cached
        assert self.factory._manager_instances[CommandType.LLM] == mock_manager_instance
    
    def test_get_manager_unsupported_command_type_raises_error(self):
        """Test getting unsupported command type raises ValueError."""
        # Create a custom command type that's not registered
        unsupported_type = "UNSUPPORTED_TYPE"
        
        with pytest.raises(ValueError, match="Unsupported command type: UNSUPPORTED_TYPE"):
            self.factory.get_manager(unsupported_type)


class TestManagerFactorySingletonBehavior:
    """Test singleton behavior of manager instances."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.factory = ManagerFactory(self.config_provider)
    
    def test_get_manager_returns_cached_instance(self):
        """Test that subsequent calls return cached instance."""
        mock_manager_class = Mock()
        mock_manager_instance = Mock(spec=Manager)
        mock_manager_class.return_value = mock_manager_instance
        
        # Replace the class in the registry
        self.factory._manager_registry[CommandType.LLM] = mock_manager_class
        
        # First call should create instance
        manager1 = self.factory.get_manager(CommandType.LLM)
        
        # Second call should return cached instance
        manager2 = self.factory.get_manager(CommandType.LLM)
        
        # Should be same instance
        assert manager1 is manager2
        assert manager1 == mock_manager_instance
        
        # Should only call constructor once
        mock_manager_class.assert_called_once()
    
    def test_different_command_types_create_different_instances(self):
        """Test that different command types create different manager instances."""
        mock_llm_class = Mock()
        mock_fs_class = Mock()
        mock_llm_instance = Mock(spec=Manager)
        mock_fs_instance = Mock(spec=Manager)
        mock_llm_class.return_value = mock_llm_instance
        mock_fs_class.return_value = mock_fs_instance
        
        # Replace classes in registry
        self.factory._manager_registry[CommandType.LLM] = mock_llm_class
        self.factory._manager_registry[CommandType.FILESYSTEM] = mock_fs_class
        
        llm_manager = self.factory.get_manager(CommandType.LLM)
        fs_manager = self.factory.get_manager(CommandType.FILESYSTEM)
        
        # Should be different instances
        assert llm_manager is not fs_manager
        assert llm_manager == mock_llm_instance
        assert fs_manager == mock_fs_instance
        
        # Both should be cached separately
        assert self.factory._manager_instances[CommandType.LLM] == mock_llm_instance
        assert self.factory._manager_instances[CommandType.FILESYSTEM] == mock_fs_instance


class TestManagerFactoryCleanup:
    """Test manager factory cleanup functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.factory = ManagerFactory(self.config_provider)
    
    @pytest.mark.asyncio
    async def test_close_all_calls_close_on_all_managers(self):
        """Test that close_all calls close on all created managers."""
        mock_llm_class = Mock()
        mock_fs_class = Mock()
        mock_llm_instance = Mock(spec=Manager)
        mock_fs_instance = Mock(spec=Manager)
        mock_llm_instance.close = AsyncMock()
        mock_fs_instance.close = AsyncMock()
        mock_llm_class.return_value = mock_llm_instance
        mock_fs_class.return_value = mock_fs_instance
        
        # Replace classes in registry
        self.factory._manager_registry[CommandType.LLM] = mock_llm_class
        self.factory._manager_registry[CommandType.FILESYSTEM] = mock_fs_class
        
        # Create some manager instances
        llm_manager = self.factory.get_manager(CommandType.LLM)
        fs_manager = self.factory.get_manager(CommandType.FILESYSTEM)
        
        # Close all managers
        await self.factory.close_all()
        
        # Should call close on all instances
        mock_llm_instance.close.assert_called_once()
        mock_fs_instance.close.assert_called_once()
        
        # Should clear instances cache
        assert len(self.factory._manager_instances) == 0
    
    @pytest.mark.asyncio
    async def test_close_all_with_no_managers_does_not_error(self):
        """Test that close_all with no created managers doesn't error."""
        # Should not raise any exception
        await self.factory.close_all()
        
        # Cache should still be empty
        assert len(self.factory._manager_instances) == 0
    
    @pytest.mark.asyncio
    async def test_close_all_fails_on_manager_close_error(self):
        """Test that close_all fails when a manager close fails."""
        mock_llm_class = Mock()
        mock_web_class = Mock()
        mock_llm_instance = Mock(spec=Manager)
        mock_web_instance = Mock(spec=Manager)
        
        # Make one manager fail to close
        mock_llm_instance.close = AsyncMock(side_effect=RuntimeError("Close failed"))
        mock_web_instance.close = AsyncMock()
        
        mock_llm_class.return_value = mock_llm_instance
        mock_web_class.return_value = mock_web_instance
        
        # Replace classes in registry
        self.factory._manager_registry[CommandType.LLM] = mock_llm_class
        self.factory._manager_registry[CommandType.WEB] = mock_web_class
        
        # Create manager instances
        self.factory.get_manager(CommandType.LLM)
        self.factory.get_manager(CommandType.WEB)
        
        # close_all should raise the error from failing manager
        with pytest.raises(RuntimeError, match="Close failed"):
            await self.factory.close_all()
        
        # Instances should not be cleared since close_all failed
        assert len(self.factory._manager_instances) == 2


class TestManagerFactoryEdgeCases:
    """Test edge cases and error conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        config_dict = {}
        self.config_provider = ConfigProvider(config_dict)
        self.factory = ManagerFactory(self.config_provider)
    
    def test_manager_creation_with_manager_constructor_error(self):
        """Test behavior when manager constructor raises an error."""
        mock_manager_class = Mock()
        mock_manager_class.side_effect = RuntimeError("Manager creation failed")
        
        # Replace class in registry
        self.factory._manager_registry[CommandType.LLM] = mock_manager_class
        
        with pytest.raises(RuntimeError, match="Manager creation failed"):
            self.factory.get_manager(CommandType.LLM)
        
        # Failed instance should not be cached
        assert CommandType.LLM not in self.factory._manager_instances
    
    def test_factory_state_after_manager_creation_error(self):
        """Test that factory state remains consistent after manager creation error."""
        mock_fs_class = Mock()
        mock_llm_class = Mock()
        
        # First manager succeeds
        mock_fs_instance = Mock(spec=Manager)
        mock_fs_class.return_value = mock_fs_instance
        
        # Second manager fails
        mock_llm_class.side_effect = RuntimeError("LLM creation failed")
        
        # Replace classes in registry
        self.factory._manager_registry[CommandType.FILESYSTEM] = mock_fs_class
        self.factory._manager_registry[CommandType.LLM] = mock_llm_class
        
        # Create successful manager first
        fs_manager = self.factory.get_manager(CommandType.FILESYSTEM)
        assert fs_manager == mock_fs_instance
        
        # Try to create failing manager
        with pytest.raises(RuntimeError, match="LLM creation failed"):
            self.factory.get_manager(CommandType.LLM)
        
        # Successful manager should still be cached
        assert self.factory._manager_instances[CommandType.FILESYSTEM] == mock_fs_instance
        assert CommandType.LLM not in self.factory._manager_instances
        
        # Should still be able to get successful manager
        fs_manager2 = self.factory.get_manager(CommandType.FILESYSTEM)
        assert fs_manager2 is fs_manager


class TestManagerFactoryIntegration:
    """Test integration scenarios."""
    
    def test_realistic_manager_usage_pattern(self):
        """Test realistic pattern of manager usage."""
        config_dict = {
            'api_keys': {'openai': 'test-key'},
            'web_config': {'browser': 'chrome'}
        }
        config_provider = ConfigProvider(config_dict)
        factory = ManagerFactory(config_provider)
        
        mock_llm_class = Mock()
        mock_web_class = Mock()
        mock_llm_instance = Mock(spec=Manager)
        mock_web_instance = Mock(spec=Manager)
        mock_llm_class.return_value = mock_llm_instance
        mock_web_class.return_value = mock_web_instance
        
        # Replace classes in registry
        factory._manager_registry[CommandType.LLM] = mock_llm_class
        factory._manager_registry[CommandType.WEB] = mock_web_class
        
        # Simulate typical usage pattern
        # 1. Get LLM manager multiple times (for multiple LLM calls)
        llm1 = factory.get_manager(CommandType.LLM)
        llm2 = factory.get_manager(CommandType.LLM)
        llm3 = factory.get_manager(CommandType.LLM)
        
        # 2. Get web manager (for web automation)
        web1 = factory.get_manager(CommandType.WEB)
        
        # 3. Get LLM manager again (for processing web results)
        llm4 = factory.get_manager(CommandType.LLM)
        
        # All LLM managers should be same instance
        assert llm1 is llm2 is llm3 is llm4
        assert llm1 == mock_llm_instance
        
        # Web manager should be different from LLM manager
        assert web1 == mock_web_instance
        assert web1 is not llm1
        
        # Only one instance of each should be created
        mock_llm_class.assert_called_once_with(config_provider)
        mock_web_class.assert_called_once_with(config_provider)
    
    @pytest.mark.asyncio
    async def test_complete_lifecycle_with_cleanup(self):
        """Test complete lifecycle from creation to cleanup."""
        config_dict = {}
        config_provider = ConfigProvider(config_dict)
        factory = ManagerFactory(config_provider)
        
        mock_llm_class = Mock()
        mock_fs_class = Mock()
        mock_llm_instance = Mock(spec=Manager)
        mock_fs_instance = Mock(spec=Manager)
        mock_llm_instance.close = AsyncMock()
        mock_fs_instance.close = AsyncMock()
        mock_llm_class.return_value = mock_llm_instance
        mock_fs_class.return_value = mock_fs_instance
        
        # Replace classes in registry
        factory._manager_registry[CommandType.LLM] = mock_llm_class
        factory._manager_registry[CommandType.FILESYSTEM] = mock_fs_class
        
        # Create managers
        llm_manager = factory.get_manager(CommandType.LLM)
        fs_manager = factory.get_manager(CommandType.FILESYSTEM)
        
        # Verify creation
        assert len(factory._manager_instances) == 2
        assert factory._manager_instances[CommandType.LLM] == mock_llm_instance
        assert factory._manager_instances[CommandType.FILESYSTEM] == mock_fs_instance
        
        # Cleanup
        await factory.close_all()
        
        # Verify cleanup
        mock_llm_instance.close.assert_called_once()
        mock_fs_instance.close.assert_called_once()
        assert len(factory._manager_instances) == 0
        
        # Should be able to create new instances after cleanup
        llm_manager2 = factory.get_manager(CommandType.LLM)
        assert llm_manager2 == mock_llm_instance
        assert len(factory._manager_instances) == 1
    
    def test_real_manager_creation_integration(self):
        """Test creating real manager instances for integration verification."""
        config_dict = {'api_keys': {'test': 'value'}}
        config_provider = ConfigProvider(config_dict)
        factory = ManagerFactory(config_provider)
        
        # Test that factory can create real instances without errors
        # Note: We patch the manager constructors to avoid dependencies
        with patch.object(LLMManager, '__init__', return_value=None):
            with patch.object(FSManager, '__init__', return_value=None):
                with patch.object(WebManager, '__init__', return_value=None):
                    
                    llm_manager = factory.get_manager(CommandType.LLM)
                    fs_manager = factory.get_manager(CommandType.FILESYSTEM)
                    web_manager = factory.get_manager(CommandType.WEB)
                    
                    # Should be correct types
                    assert isinstance(llm_manager, LLMManager)
                    assert isinstance(fs_manager, FSManager)
                    assert isinstance(web_manager, WebManager)
                    
                    # Should be cached
                    assert len(factory._manager_instances) == 3
                    assert factory._manager_instances[CommandType.LLM] is llm_manager
                    assert factory._manager_instances[CommandType.FILESYSTEM] is fs_manager
                    assert factory._manager_instances[CommandType.WEB] is web_manager