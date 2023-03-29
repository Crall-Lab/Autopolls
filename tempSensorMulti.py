"""
    Modified MCC 134 probe:
    Purpose:
        Read a single data value for each channel and write to csv file in /mnt/data/tempProbes/
        Each day creates a new CSV file
        Temp probe 1 is to be paired with camera 1, and so on
        CPU is cpu temperature in deg C
"""
#%
import csv
import datetime
import os
import time
import numpy as np
from time import sleep
from sys import stdout
from daqhats import mcc134, HatIDs, HatError, TcTypes
from daqhats_utils import select_hat_device, tc_type_to_string
import gpiozero as gz
#%%

in1 = open('/etc/hostname','r')
hst1 = in1.readline().split('\n')[0]
in1.close()

ds1 = datetime.datetime.fromtimestamp(time.time())
tempName = str(ds1.year)+'-'+str(ds1.month)+'-'+str(ds1.day)+'.csv'
tempName1 = hst1+'_'+tempName

if os.path.isdir('/mnt/data/tempProbes/') == False:
    os.mkdir('/mnt/data/tempProbes/')
    
if os.path.isfile('/mnt/data/tempProbes/'+tempName1) == False: #make new file everyday??
    f = open('/mnt/data/tempProbes/'+tempName1, 'w')
    writer = csv.writer(f)
    heads = ['date','time','probe1','probe2','probe3','probe4','cpu']
    writer.writerow(heads)
    f.close()
cpu1 = str(gz.CPUTemperature().temperature)

# Constants
CURSOR_BACK_2 = '\x1b[2D'
ERASE_TO_END_OF_LINE = '\x1b[0K'


def main():
    """
    This function is executed automatically when the module is run directly.
    """
    ds1 = datetime.datetime.fromtimestamp(time.time())
    tempName = str(ds1.year)+'-'+str(ds1.month)+'-'+str(ds1.day)+'.csv'
    tempName1 = hst1+'_'+tempName

    tc_type = TcTypes.TYPE_T   # change this to the desired thermocouple type
    delay_between_reads = 1  # Seconds
    channels = (0, 1, 2, 3)

    try:
        # Get an instance of the selected hat device object.
        address = select_hat_device(HatIDs.MCC_134)
        hat = mcc134(address)

        for channel in channels:
            hat.tc_type_write(channel, tc_type)

        try:
            probVa = []
            for channel in channels:
                value = hat.t_in_read(channel)
                if value == mcc134.OPEN_TC_VALUE:
                    probVa.append(np.nan)
                elif value == mcc134.OVERRANGE_TC_VALUE:
                    probVa.append(np.nan)
                elif value == mcc134.COMMON_MODE_TC_VALUE:
                    probVa.append(np.nan)
                else:
                    probVa.append('{:3.2f}'.format(value))

                stdout.flush()

                # Wait the specified interval between reads.
            tstamp = '%02d'%ds1.hour+':'+'%02d'%ds1.minute+':'+'%02d'%ds1.second
            finalLine = [tempName.split('.')[0],tstamp,probVa[0],probVa[1],probVa[2],probVa[3],cpu1]
            f = open('/mnt/data/tempProbes/'+tempName1, 'a')
            writer = csv.writer(f)
            writer.writerow(finalLine)
            f.close()
            
        except KeyboardInterrupt:
            # Clear the '^C' from the display.
            print(CURSOR_BACK_2, ERASE_TO_END_OF_LINE, '\n')

    except (HatError, ValueError) as error:
        print('\n', error)


if __name__ == '__main__':
    # This will only be run when the module is called directly.
    t1 = time.time()
    for ele in range(0,9):
        if ele != 0:
            time.sleep(3)
        main()

