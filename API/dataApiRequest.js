import * as axios from "axios";

const apiConst = axios.create({
	baseURL: 'https://social-network.samuraijs.com/api/1.0/',
	withCredentials: true,
	headers: {"API-KEY": "b516e719-c36d-4150-afe4-048d0a974d23"},
});

export const dataApiRequest = {
	getUsersA(usersOnPage, choosedPage) {
		return apiConst.get(`users?count=${usersOnPage}&page=${choosedPage}`)
	},
	setUnfollow(userId) {
		return apiConst.delete(`follow/${userId}`)
	},
	setFollow(userId){
		return apiConst.post(`follow/${userId}`, {}, {})
	},
	authRequest(){
		return apiConst.get(`auth/me`)
	},
	profileRequest(UserId){
		return apiConst.get(`profile/${UserId ? UserId : '2'}`)
	}
};




