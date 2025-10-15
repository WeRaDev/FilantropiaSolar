# FilantropiaSolar Agent Profile Creation Checklist

## ✅ Profile Creation Steps

### Step 1: Access Settings
- [ ] Warp Terminal is open
- [ ] Press `⌘+,` (Cmd+Comma) to open Settings
- [ ] Navigate to **AI Agent** → **Profiles** in the left sidebar

### Step 2: Create New Profile
- [ ] Click **"Create New Profile"** or **"+"** button
- [ ] New profile form opens

### Step 3: Basic Information
```
Profile Name: FilantropiaSolar-Dev
Description: Dedicated agent for FilantropiaSolar development tasks
```
- [ ] Name entered: `FilantropiaSolar-Dev`
- [ ] Description entered

### Step 4: Directory Permissions
```
Allowed Directories:
/Users/mikhailananyin/Documents/FilantropiaSolar
```
- [ ] Added project directory path
- [ ] Verified path is correct

### Step 5: Command Permissions
```
Essential Commands:
✅ python
✅ pip  
✅ git
✅ docker
✅ pytest
✅ make
✅ ruff
✅ black
✅ ls
✅ cat
✅ find
✅ tree
```
- [ ] All essential commands added
- [ ] No unnecessary system commands included

### Step 6: File Operation Permissions
```
File Operations:
✅ Read files in allowed directories
✅ Write files in allowed directories  
✅ Execute scripts in allowed directories
❌ System-wide file access (should be restricted)
```
- [ ] Read permission: Enabled for project directory
- [ ] Write permission: Enabled for project directory
- [ ] Execute permission: Enabled for project directory
- [ ] System access: Restricted/Disabled

### Step 7: Save and Verify
- [ ] Click **"Save Profile"** or **"Create"** button
- [ ] Profile appears in the profiles list
- [ ] **Profile ID generated** (note it down below)

## 📝 Profile Information (Fill after creation)

```
Profile Name: FilantropiaSolar-Dev
Profile ID: ________________________________
Creation Date: ________________________________
Status: ________________________________
```

## 🧪 Verification Steps (Run after creation)

### Check Profile List
```bash
warp agent profile list
```
Expected output should show your new profile.

### Test Basic Functionality
```bash
warp agent run --profile <PROFILE-ID> --prompt "list the main directories in this project" --cwd "/Users/mikhailananyin/Documents/FilantropiaSolar"
```

### Test File Operations
```bash
warp agent run --profile <PROFILE-ID> --prompt "check if main.py exists and show its first 10 lines" --cwd "/Users/mikhailananyin/Documents/FilantropiaSolar"
```

### Test Development Commands
```bash
warp agent run --profile <PROFILE-ID> --prompt "run 'python --version' to check Python version" --cwd "/Users/mikhailananyin/Documents/FilantropiaSolar"
```

## 🚨 Troubleshooting

### Common Issues:
1. **Profile not appearing**: Wait a few seconds and refresh, or restart Warp
2. **Permission denied**: Check that directory path is exact
3. **Command not allowed**: Verify command is in allowed list
4. **Profile ID not working**: Use the exact ID from the profile list

### If Issues Occur:
1. Double-check all settings match the specifications
2. Try deleting and recreating the profile
3. Verify Warp is up to date
4. Check that no typos in directory path

## ✅ Success Criteria

Profile creation is successful when:
- [ ] Profile appears in `warp agent profile list`
- [ ] Basic test command works with the profile ID
- [ ] File operations work within project directory
- [ ] Commands are restricted to allowed list
- [ ] No system-wide access granted

---

**Next Step**: Once profile is created, run verification commands and update WARP_AGENT_SETUP.md with the actual Profile ID.