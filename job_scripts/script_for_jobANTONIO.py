#!/bin/bash

# =============================================================================
# Automated Optical Measurement Script for ANTONIO MICRO RING DYNAMICS
# =============================================================================

i=1


# SET RESONANCE WAVELENGHT HERE
resonanceWL=1553.67
upper_blueshift=1554
lower_redshift=1553
Lamda_steps=0.05


echo "################"
echo "STARTING MEASUREMENT"
echo "################"

# Turn on 81949A model case with 8163B Tunable Laser
set_LASER_81949Atunablelaser --slot 1 status
set_LASER_81949Atunablelaser --slot 1 output on

# Initial Santec attenuator value
set_optical_attenuator --action set_attenuation --value 90

# Sweep laser power
#for laser_power in $(seq 6 1 11); do
for laser_power in 8 10 12; do
  echo "################"
  echo "Laser power set to ${laser_power} dBm"
  echo "################"

  set_LASER_81949Atunablelaser --slot 1 set-pwr "${laser_power}"

  # Sweep atten (dB label)
  for power_dB in 40; do
  #for power_dB in $(seq 10 -5 0); do
    echo "################"
    echo "Attenuator set to ${power_dB} dB"
    echo "################"

    set_optical_attenuator --action set_attenuation --value "${power_dB}"

      ##########################################################################################################################
                          #BLUE SHIFT SCAN STARTS FROM HERE
      ##########################################################################################################################
      # Sweep 81949A model case with 8163B Tunable Laser wavelength (nm label per user request) BLUE SHIFT SCAN
      #for wavelength in 1556; do
      for wavelength in $(seq ${resonanceWL} ${Lamda_steps} ${upper_blueshift}); do
          echo "################"
          echo "Keysight_8163B set to ${wavelength} nm"
          echo "################"

          set_LASER_81949Atunablelaser --slot 1 set-wl "${wavelength}"
          sleep 2
          # Acquire from the Keysight InfiniiVision 2000X
          get_keysight_infiniivision_2000x -c CHAN3,CHAN4 -f "OSCwaveform_${i}_BLUESHIFT_FROM_${resonanceWL}_SCAN_${wavelength}nm_LD${laser_power}dBm_1kbps${power_dB}dB" --force

          i=$((i + 1))
          sleep 0
      done

      ##########################################################################################################################
                              #RED SHIFT SCAN STARTS FROM HERE
      ##########################################################################################################################

      for wavelength in $(seq ${resonanceWL} -${Lamda_steps} ${lower_redshift}); do
          echo "################"
          echo "Keysight_8163B set to ${wavelength} nm"
          echo "################"

          set_LASER_81949Atunablelaser --slot 1 set-wl "${wavelength}"
          sleep 2
          # Acquire from the Keysight InfiniiVision 2000X
          get_keysight_infiniivision_2000x -c CHAN3,CHAN4 -f "OSCwaveform_${i}_REDSHIFT_FROM_${resonanceWL}_SCAN_${wavelength}nm_LD${laser_power}dBm_1kbps${power_dB}dB" --force

          i=$((i + 1))
          sleep 0
      done

    echo '######################################'
    echo 'FINISHED CUR LOOP'
    echo '######################################'

  done
done

echo '######################################'
echo 'FINISHED LOOP'
echo '######################################'

echo 'FINISHING MEASUREMENT, TURNING LASER OFF AND CHECKING STATE'
set_LASER_81949Atunablelaser --slot 1 output off
set_optical_attenuator --action set_attenuation --value 90
echo 'FINISHING MEASUREMENT'
