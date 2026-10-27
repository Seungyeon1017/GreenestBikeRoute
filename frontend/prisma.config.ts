import 'dotenv/config' // for Prisma 7
import { defineConfig } from '@prisma/config'

export default defineConfig({
  schema: './prisma/schema.prisma',

  // required: move your database URL here
  datasource: {
    url: process.env.DATABASE_URL!,
  },
})
