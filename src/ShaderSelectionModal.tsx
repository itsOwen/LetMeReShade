// src/ShaderSelectionModal.tsx
import { useState, useEffect } from "react";
import {
  ConfirmModal,
  ToggleField
} from "@decky/ui";
import { callable } from "@decky/api";

interface ShaderPackage {
  id: string;
  name: string;
  description: string;
  file: string;
  size_mb: string;
  enabled: boolean;
}

interface ShaderSelectionResponse {
  status: string;
  shaders?: ShaderPackage[];
  total_count?: number;
  message?: string;
}

interface ShaderSelectionModalProps {
  onConfirm: (selectedShaders: string[]) => void;
  onCancel: () => void;
  addonEnabled: boolean;
  autoHdrEnabled: boolean;
  selectedVersion: string;
  closeModal?: () => void;
  mode?: 'install' | 'manage'; // New prop for mode
  initialSelectedShaders?: string[]; // New prop for pre-selected shaders
}

const getAvailableShaders = callable<[], ShaderSelectionResponse>("get_available_shaders");
const logError = callable<[string], void>("log_error");

const ShaderSelectionModal = ({
  onConfirm,
  onCancel,
  addonEnabled,
  autoHdrEnabled,
  selectedVersion,
  closeModal,
  mode = 'install',
  initialSelectedShaders = []
}: ShaderSelectionModalProps) => {
  const [shaderPackages, setShaderPackages] = useState<ShaderPackage[]>([]);
  const [selectedShaders, setSelectedShaders] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    loadAvailableShaders();
  }, []);

  useEffect(() => {
    // Initialize with saved preferences if provided
    if (initialSelectedShaders.length > 0) {
      const initialSet = new Set(initialSelectedShaders);
      setSelectedShaders(initialSet);
      setSelectAll(initialSelectedShaders.length === shaderPackages.length);
    }
  }, [initialSelectedShaders, shaderPackages]);

  const loadAvailableShaders = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await getAvailableShaders();
      
      if (response.status === "success" && response.shaders) {
        setShaderPackages(response.shaders);
        
        // Initialize based on mode and initial selections
        if (initialSelectedShaders.length > 0) {
          const initialSet = new Set(initialSelectedShaders);
          setSelectedShaders(initialSet);
          setSelectAll(initialSelectedShaders.length === response.shaders.length);
        } else {
          // Default behavior: select all shaders
          const allShaderIds = new Set(response.shaders.map(shader => shader.id));
          setSelectedShaders(allShaderIds);
          setSelectAll(true);
        }
      } else {
        setError(response.message || 'Failed to load shader packages');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(`Error loading shaders: ${errorMsg}`);
      await logError(`ShaderSelectionModal -> loadAvailableShaders: ${errorMsg}`);
    } finally {
      setLoading(false);
    }
  };

  const handleShaderToggle = (shaderId: string, enabled: boolean) => {
    const newSelectedShaders = new Set(selectedShaders);
    
    if (enabled) {
      newSelectedShaders.add(shaderId);
    } else {
      newSelectedShaders.delete(shaderId);
    }
    
    setSelectedShaders(newSelectedShaders);
    
    // Update select all state
    setSelectAll(newSelectedShaders.size === shaderPackages.length);
  };

  const handleSelectAllToggle = (enabled: boolean) => {
    if (enabled) {
      // Select all shaders
      const allShaderIds = new Set(shaderPackages.map(shader => shader.id));
      setSelectedShaders(allShaderIds);
    } else {
      // Deselect all shaders
      setSelectedShaders(new Set());
    }
    setSelectAll(enabled);
  };

  const handleConfirm = () => {
    const selectedShaderIds = Array.from(selectedShaders);
    onConfirm(selectedShaderIds);
    if (closeModal) closeModal();
  };

  const handleCancel = () => {
    onCancel();
    if (closeModal) closeModal();
  };

  const calculateTotalSize = () => {
    let totalSize = 0;
    shaderPackages.forEach(shader => {
      if (selectedShaders.has(shader.id)) {
        // Parse size from string like "15.2MB" to number
        const sizeMatch = shader.size_mb.match(/(\d+\.?\d*)/);
        if (sizeMatch) {
          totalSize += parseFloat(sizeMatch[1]);
        }
      }
    });
    return totalSize.toFixed(1);
  };

  const getModalTitle = () => {
    return mode === 'manage' ? 'Manage Shader Preferences' : 'Select Shader Packages';
  };

  const getConfirmButtonText = () => {
    return mode === 'manage' ? 'Save Preferences' : 'Install';
  };

  const getInstallSummary = () => {
    const selectedCount = selectedShaders.size;
    const totalCount = shaderPackages.length;
    
    if (mode === 'manage') {
      return `Shader Packages: ${selectedCount}/${totalCount} selected\nThese preferences will be used for future installations.`;
    }
    
    let summary = `Installing ReShade ${selectedVersion.charAt(0).toUpperCase() + selectedVersion.slice(1)}`;
    
    if (addonEnabled) {
      summary += " with Addon Support";
    }
    
    if (autoHdrEnabled) {
      summary += " + AutoHDR";
    }
    
    summary += `\n\nShader Packages: ${selectedCount}/${totalCount} selected`;
    
    if (selectedCount > 0) {
      summary += ` (~${calculateTotalSize()}MB)`;
    }
    
    return summary;
  };

  const getDescription = () => {
    if (mode === 'manage') {
      return (
        <div style={{ 
          textAlign: 'left', 
          maxHeight: '60vh', 
          overflowY: 'auto',
          fontSize: '0.9em',
          lineHeight: '1.3',
          paddingRight: '8px'
        }}>
          {loading ? (
            <div style={{ padding: '20px', textAlign: 'center' }}>
              Loading shader packages...
            </div>
          ) : error ? (
            <div style={{ 
              padding: '12px', 
              backgroundColor: '#ff6b6b', 
              borderRadius: '4px', 
              color: 'white',
              marginBottom: '12px',
              fontSize: '0.85em'
            }}>
              {error}
            </div>
          ) : (
            <>
              <div style={{ marginBottom: '12px', fontSize: '0.85em', opacity: 0.8 }}>
                Configure your preferred shader packages. These selections will be automatically used for future ReShade installations.
              </div>
              
              <div 
                style={{ 
                  marginBottom: '12px',
                  padding: '8px',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '4px',
                  backgroundColor: 'rgba(255,255,255,0.05)'
                }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  maxWidth: '100%'
                }}>
                  <div style={{ 
                    flex: '1', 
                    marginRight: '12px',
                    fontSize: '0.9em',
                    fontWeight: 'bold'
                  }}>
                    Select All ({shaderPackages.length} packages)
                  </div>
                  <div style={{ 
                    flexShrink: 0,
                    width: '65px',
                    height: '35px',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    overflow: 'hidden',
                    position: 'relative'
                  }}>
                    <div style={{
                      maxWidth: '60px',
                      maxHeight: '32px',
                      overflow: 'hidden'
                    }}>
                      <ToggleField
                        checked={selectAll}
                        onChange={handleSelectAllToggle}
                      />
                    </div>
                  </div>
                </div>
              </div>
              
              {shaderPackages.map((shader) => (
                <div 
                  key={shader.id} 
                  style={{ 
                    marginBottom: '8px', 
                    padding: '8px', 
                    border: '1px solid rgba(255,255,255,0.1)', 
                    borderRadius: '4px',
                    backgroundColor: 'rgba(255,255,255,0.02)'
                  }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'flex-start',
                    maxWidth: '100%'
                  }}>
                    <div style={{ 
                      flex: '1', 
                      marginRight: '12px',
                      minWidth: 0
                    }}>
                      <div style={{ 
                        fontWeight: 'bold', 
                        fontSize: '0.85em',
                        marginBottom: '2px',
                        wordWrap: 'break-word',
                        overflow: 'hidden'
                      }}>
                        {shader.name}
                      </div>
                      <div style={{ 
                        fontSize: '0.75em', 
                        opacity: 0.8, 
                        marginBottom: '4px',
                        wordWrap: 'break-word',
                        lineHeight: '1.2',
                        overflow: 'hidden'
                      }}>
                        {shader.description}
                      </div>
                      <div style={{ 
                        fontSize: '0.7em', 
                        opacity: 0.6,
                        fontStyle: 'italic'
                      }}>
                        Size: {shader.size_mb}
                      </div>
                    </div>
                    <div style={{ 
                      flexShrink: 0,
                      width: '65px',
                      height: '35px',
                      display: 'flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      marginTop: '2px',
                      overflow: 'hidden',
                      position: 'relative'
                    }}>
                      <div style={{
                        maxWidth: '60px',
                        maxHeight: '32px',
                        overflow: 'hidden'
                      }}>
                        <ToggleField
                          checked={selectedShaders.has(shader.id)}
                          onChange={(enabled) => handleShaderToggle(shader.id, enabled)}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              
              <div 
                style={{ 
                  marginTop: '12px', 
                  padding: '10px', 
                  backgroundColor: 'rgba(255,255,255,0.1)', 
                  borderRadius: '4px',
                  fontSize: '0.8em',
                  border: '1px solid rgba(255,255,255,0.15)'
                }}>
                <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>
                  {mode === 'manage' ? 'Preferences Summary:' : 'Installation Summary:'}
                </div>
                <div style={{ whiteSpace: 'pre-line', lineHeight: '1.3' }}>{getInstallSummary()}</div>
              </div>
            </>
          )}
        </div>
      );
    }

    // Return the original description for install mode
    return (
      <div style={{ 
        textAlign: 'left', 
        maxHeight: '60vh', 
        overflowY: 'auto',
        fontSize: '0.9em',
        lineHeight: '1.3',
        paddingRight: '8px'
      }}>
        {loading ? (
          <div style={{ padding: '20px', textAlign: 'center' }}>
            Loading shader packages...
          </div>
        ) : error ? (
          <div style={{ 
            padding: '12px', 
            backgroundColor: '#ff6b6b', 
            borderRadius: '4px', 
            color: 'white',
            marginBottom: '12px',
            fontSize: '0.85em'
          }}>
            {error}
          </div>
        ) : (
          <>
            <div style={{ marginBottom: '12px', fontSize: '0.85em', opacity: 0.8 }}>
              Choose which shader packages to install. You can add more later.
            </div>
            
            <div 
              style={{ 
                marginBottom: '12px',
                padding: '8px',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '4px',
                backgroundColor: 'rgba(255,255,255,0.05)'
              }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                maxWidth: '100%'
              }}>
                <div style={{ 
                  flex: '1', 
                  marginRight: '12px',
                  fontSize: '0.9em',
                  fontWeight: 'bold'
                }}>
                  Select All ({shaderPackages.length} packages)
                </div>
                <div style={{ 
                  flexShrink: 0,
                  width: '65px',
                  height: '35px',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  overflow: 'hidden',
                  position: 'relative'
                }}>
                  <div style={{
                    maxWidth: '60px',
                    maxHeight: '32px',
                    overflow: 'hidden'
                  }}>
                    <ToggleField
                      checked={selectAll}
                      onChange={handleSelectAllToggle}
                    />
                  </div>
                </div>
              </div>
            </div>
            
            {shaderPackages.map((shader) => (
              <div 
                key={shader.id} 
                style={{ 
                  marginBottom: '8px', 
                  padding: '8px', 
                  border: '1px solid rgba(255,255,255,0.1)', 
                  borderRadius: '4px',
                  backgroundColor: 'rgba(255,255,255,0.02)'
                }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'flex-start',
                  maxWidth: '100%'
                }}>
                  <div style={{ 
                    flex: '1', 
                    marginRight: '12px',
                    minWidth: 0
                  }}>
                    <div style={{ 
                      fontWeight: 'bold', 
                      fontSize: '0.85em',
                      marginBottom: '2px',
                      wordWrap: 'break-word',
                      overflow: 'hidden'
                    }}>
                      {shader.name}
                    </div>
                    <div style={{ 
                      fontSize: '0.75em', 
                      opacity: 0.8, 
                      marginBottom: '4px',
                      wordWrap: 'break-word',
                      lineHeight: '1.2',
                      overflow: 'hidden'
                    }}>
                      {shader.description}
                    </div>
                    <div style={{ 
                      fontSize: '0.7em', 
                      opacity: 0.6,
                      fontStyle: 'italic'
                    }}>
                      Size: {shader.size_mb}
                    </div>
                  </div>
                  <div style={{ 
                    flexShrink: 0,
                    width: '65px',
                    height: '35px',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    marginTop: '2px',
                    overflow: 'hidden',
                    position: 'relative'
                  }}>
                    <div style={{
                      maxWidth: '60px',
                      maxHeight: '32px',
                      overflow: 'hidden'
                    }}>
                      <ToggleField
                        checked={selectedShaders.has(shader.id)}
                        onChange={(enabled) => handleShaderToggle(shader.id, enabled)}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
            
            <div 
              style={{ 
                marginTop: '12px', 
                padding: '10px', 
                backgroundColor: 'rgba(255,255,255,0.1)', 
                borderRadius: '4px',
                fontSize: '0.8em',
                border: '1px solid rgba(255,255,255,0.15)'
              }}>
              <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>Installation Summary:</div>
              <div style={{ whiteSpace: 'pre-line', lineHeight: '1.3' }}>{getInstallSummary()}</div>
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <ConfirmModal
      strTitle={getModalTitle()}
      strDescription={getDescription()}
      strOKButtonText={loading ? "Loading..." : getConfirmButtonText()}
      strCancelButtonText="Cancel"
      onOK={handleConfirm}
      onCancel={handleCancel}
      bOKDisabled={loading || error !== '' || selectedShaders.size === 0}
    />
  );
};

export default ShaderSelectionModal;