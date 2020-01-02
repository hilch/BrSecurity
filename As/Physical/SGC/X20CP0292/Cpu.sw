<?xml version="1.0" encoding="utf-8"?>
<?AutomationStudio Version=4.6.3.55 SP?>
<SwConfiguration CpuAddress="SL1" xmlns="http://br-automation.co.at/AS/SwConfiguration">
  <TaskClass Name="Cyclic#1" />
  <TaskClass Name="Cyclic#2" />
  <TaskClass Name="Cyclic#3" />
  <TaskClass Name="Cyclic#4">
    <Task Name="Passwd" Source="Examples.Passwd.prg" Memory="UserROM" Language="IEC" Debugging="true" />
    <Task Name="Blowfish" Source="Examples.Blowfish.prg" Memory="UserROM" Language="IEC" Debugging="true" />
  </TaskClass>
  <Libraries>
    <LibraryObject Name="BrSecurity" Source="Libraries.BrSecurity.lby" Memory="UserROM" Language="ANSIC" Debugging="true" />
    <LibraryObject Name="AsBrStr" Source="Libraries.AsBrStr.lby" Memory="UserROM" Language="binary" Debugging="true" />
  </Libraries>
</SwConfiguration>