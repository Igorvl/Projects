import * as axios from "axios";

export const getApiUsers = (usersOnPage, choosedPage) => {
	const axCreate = axios.create({
		baseURL: 'https://social-network.samuraijs.com/api/1.0/',
		withCredentials: true,
		headers: {"API-KEY": "b516e719-c36d-4150-afe4-048d0a974d23"},
	});
	return axCreate.get(`users?count=${usersOnPage}&page=${choosedPage}`)
};


