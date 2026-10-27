import { ReactECharts } from '@/components/Charts/ReactECharts'

export default function DistanceBar() {
  return (
    <ReactECharts
      option={{
        title: {
          text: 'Average Distance (cm)',
          left: 'center',

          padding: [0, 0, 0, 0],
          textStyle: {
            fontSize: 16,
            fontWeight: 'bold',
            color: 'white',
          },
        },
        grid: {
          left: '3%',
          right: '2%',
          top: '10%',
          bottom: '0',
          containLabel: true,
        },
        xAxis: {
          type: 'value',
          min: 0,
          max: 200,
          interval: 50,
          axisLabel: {
            formatter: '{value}.0',
            color: 'white',
          },
          axisLine: {
            show: true,
            lineStyle: {
              color: 'white',
            },
          },
          splitLine: { show: false },
          axisTick: {
            show: true,
          },
        },
        yAxis: {
          type: 'category',
          position: 'bottom',
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          offset: -10,
          data: [''],
        },
        series: [
          {
            name: 'Distance',
            type: 'bar',
            barWidth: '50%',
            barGap: '0%',
            data: [200],
            itemStyle: {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 1,
                y2: 0,
                colorStops: [
                  { offset: 0.07, color: 'rgba(252,12,3,1)' },
                  { offset: 0.27, color: 'rgba(246,98,15,1)' },
                  { offset: 0.48, color: 'rgba(239,235,37,1)' },
                  { offset: 0.69, color: 'rgba(153,255,87,1)' },
                  { offset: 1, color: 'rgba(0,128,0,1)' },
                ],
              },
              borderRadius: [0, 4, 4, 0],
            },
            label: { show: false },
          },
        ],
      }}
      style={{ height: '65px', width: '200px' }}
    />
  )
}
